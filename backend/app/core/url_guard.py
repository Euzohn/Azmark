"""SSRF guard for user-supplied outbound base URLs (spec #70).

``base_url`` values for LLM and search providers are written by authenticated
users and requested server-side by httpx.  To stop the server being used as a
proxy into the deployment's private network, we enforce:

- scheme must be http/https (no file://, gopher://, dict://, ...);
- the host must not target non-global address space (loopback, private,
  link-local, reserved, multicast, unspecified) — checked on IP literals and,
  best-effort, on DNS answers;
- ``localhost`` and its subdomains are rejected by name.

Resolution is validated best-effort: an unresolvable host is accepted because
the check cannot prove anything non-global.  Operators who intentionally point
providers at LAN endpoints (self-hosted Ollama, local SearxNG) can set
``AZMARK_ALLOW_PRIVATE_BASE_URLS=true`` to lift the address-space check while
keeping the scheme restriction.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = ("http", "https")


def _is_non_global(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Unpack IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) before classifying, so
    # the embedded IPv4 address is what gets judged.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return not address.is_global


def validate_base_url(value: str, *, allow_private: bool = False) -> str:
    """Validate a user-supplied provider base URL.

    Returns ``value`` unchanged when accepted; raises ``ValueError`` with a
    human-readable reason otherwise.
    """
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError("base_url must use http or https")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError("base_url must include a host")
    if allow_private:
        return value
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("base_url must not target localhost")

    # Literal IP addresses classify without any DNS lookup.
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _is_non_global(address):
            raise ValueError("base_url must not target private or loopback addresses")
        return value

    # Hostname: best-effort resolution check.  DNS failure accepts the value
    # (fail-open) — nothing private could be proven at save time.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return value
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_non_global(address):
            raise ValueError("base_url resolves to a private or loopback address")
    return value
