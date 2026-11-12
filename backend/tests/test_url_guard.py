"""SSRF guard for user-supplied base_url values (spec #70)."""

import socket

import pytest

from app.core.config import settings
from app.core.url_guard import validate_base_url
from tests.conftest import auth_headers, register_and_login

# ---------------------------------------------------------------- unit guard


def test_public_https_url_accepted():
    assert validate_base_url("https://api.example.com/v1") == "https://api.example.com/v1"


def test_non_http_schemes_rejected():
    for bad in (
        "file:///etc/passwd",
        "gopher://10.0.0.1/",
        "dict://127.0.0.1:11211",
        "ftp://127.0.0.1/",
        "javascript:alert(1)",
    ):
        with pytest.raises(ValueError):
            validate_base_url(bad)


def test_missing_scheme_rejected():
    with pytest.raises(ValueError):
        validate_base_url("127.0.0.1:9000")


def test_missing_host_rejected():
    with pytest.raises(ValueError):
        validate_base_url("http://")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:9000",
        "http://10.0.0.5/",
        "http://172.16.3.4/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://0.0.0.0/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://[fe80::1]/",
        "http://[::ffff:127.0.0.1]/",
    ],
)
def test_non_global_address_literals_rejected(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


@pytest.mark.parametrize("host", ["localhost", "api.localhost", "LOCALHOST", "localhost."])
def test_localhost_names_rejected_without_dns(host):
    with pytest.raises(ValueError):
        validate_base_url(f"http://{host}/")


def test_hostname_resolving_private_rejected(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 0))]

    monkeypatch.setattr("app.core.url_guard.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError):
        validate_base_url("http://llm.internal.example/")


def test_hostname_resolving_public_accepted(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("app.core.url_guard.socket.getaddrinfo", fake_getaddrinfo)
    assert validate_base_url("http://llm.example/") == "http://llm.example/"


def test_unresolvable_hostname_accepted(monkeypatch):
    def fake_getaddrinfo(host, port):
        raise socket.gaierror("no answer")

    monkeypatch.setattr("app.core.url_guard.socket.getaddrinfo", fake_getaddrinfo)
    assert validate_base_url("http://does-not-exist.invalid/") == "http://does-not-exist.invalid/"


def test_allow_private_permits_lan_targets_but_keeps_scheme_check():
    assert validate_base_url("http://10.0.0.5:11434/", allow_private=True) == (
        "http://10.0.0.5:11434/"
    )
    with pytest.raises(ValueError):
        validate_base_url("file:///etc/passwd", allow_private=True)


# ------------------------------------------------------------------- routes


def test_ai_settings_rejects_ssrf_base_url(client):
    token = register_and_login(client, "ai_ssrf")["access_token"]
    for bad in ("http://127.0.0.1:11434", "http://10.0.0.5/v1", "file:///etc/passwd"):
        response = client.put(
            "/api/v1/settings/ai",
            json={"provider": "openai", "model": "m", "base_url": bad},
            headers=auth_headers(token),
        )
        assert response.status_code == 422, response.text


def test_ai_settings_allows_public_base_url(client):
    token = register_and_login(client, "ai_public")["access_token"]
    response = client.put(
        "/api/v1/settings/ai",
        json={"provider": "openai", "model": "m", "base_url": "https://api.example.com/v1"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text


def test_ai_settings_allow_private_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_base_urls", True)
    token = register_and_login(client, "ai_private")["access_token"]
    response = client.put(
        "/api/v1/settings/ai",
        json={"provider": "ollama", "model": "llama3", "base_url": "http://10.0.0.99:11434"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text


def test_searxng_key_rejects_ssrf_values(client):
    token = register_and_login(client, "searxng_ssrf")["access_token"]
    for bad in ("http://127.0.0.1:9000", "http://169.254.169.254/latest", "ftp://s.example"):
        response = client.put(
            "/api/v1/settings/provider-keys/searxng",
            json={"api_key": bad},
            headers=auth_headers(token),
        )
        assert response.status_code == 422, response.text


def test_searxng_key_resolution_guard(client, monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))]

    monkeypatch.setattr("app.core.url_guard.socket.getaddrinfo", fake_getaddrinfo)
    token = register_and_login(client, "searxng_dns")["access_token"]
    response = client.put(
        "/api/v1/settings/provider-keys/searxng",
        json={"api_key": "http://searx.internal/"},
        headers=auth_headers(token),
    )
    assert response.status_code == 422, response.text


def test_searxng_key_public_url_accepted(client):
    token = register_and_login(client, "searxng_ok")["access_token"]
    response = client.put(
        "/api/v1/settings/provider-keys/searxng",
        json={"api_key": "https://searx.example.com/"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text


def test_non_url_provider_keys_unaffected(client):
    token = register_and_login(client, "other_key")["access_token"]
    response = client.put(
        "/api/v1/settings/provider-keys/aviationstack",
        json={"api_key": "key-value-not-a-url"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
