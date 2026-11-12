import ipaddress
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Azmark API"
    api_v1_prefix: str = "/api/v1"
    app_version: str = "0.1.0"

    # Admin bootstrap (spec #78). Both email and password must be set; the
    # account is created/promoted only while no active admin exists.
    admin_email: str = ""
    admin_username: str = ""
    admin_password: str = ""

    database_url: str = "postgresql+psycopg://azmark:azmark@localhost:5432/azmark"

    secret_key: str = "dev-secret-change-me-please-32bytes-minimum"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # Personal access token rate limit per token (spec #69, #85). 0 disables it.
    pat_rate_limit_per_minute: int = 120

    # MCP server for external agents (spec #85), mounted at /api/v1/mcp.
    # Authenticates personal access tokens only; set false to hide the route.
    mcp_enabled: bool = True

    cors_origins: str = "http://localhost:3000"

    # Reverse-proxy trust (spec #47). Comma-separated CIDRs of the peers whose
    # X-Forwarded-For header is trusted. A direct client can forge that header,
    # so the real client address is only taken from it when the direct peer
    # (request.client.host) is one of these networks; otherwise the peer address
    # itself is used. Empty = trust nothing (safest default).
    trusted_proxies: str = ""

    aerodatabox_base_url: str = "https://aerodatabox.p.rapidapi.com"
    aerodatabox_host: str = "aerodatabox.p.rapidapi.com"
    aviationstack_base_url: str = "http://api.aviationstack.com/v1"

    # VariFlight (飞常准) Aviation MCP endpoint — see spec #66.
    variflight_mcp_url: str = "https://ai.variflight.com/servers/aviation/mcp"

    # SearchProvider (spec #37) — used for train schedules and travel lookups.
    search_provider: str = ""
    search_api_key: str = ""
    searxng_base_url: str = ""

    # Geocoding for hotel map coordinates (spec #66, Map provider). The chain is
    # configurable: Amap is preferred when a key is set (best for Chinese
    # addresses), then Photon (keyless, OSM), then Nominatim (keyless, but often
    # blocked from mainland networks — point GEOCODE_BASE_URL at a self-hosted
    # instance to lift the public rate limit).
    geocode_provider: str = "photon,nominatim"
    geocode_amap_key: str = ""
    geocode_photon_url: str = "https://photon.komoot.io"
    geocode_base_url: str = "https://nominatim.openstreetmap.org"

    # Object storage (spec #44/#75). Works with MinIO, AWS S3, R2 and OSS.
    # Empty endpoint means the AWS default endpoint.
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "azmark"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = True
    s3_addressing_style: str = "path"
    max_attachment_bytes: int = 20 * 1024 * 1024
    # Import files are UTF-8 JSON/CSV text; cap the upload so a huge file cannot
    # be read fully into memory (the attachment cap does not cover imports).
    max_import_bytes: int = 10 * 1024 * 1024

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_proxy_networks(
        self,
    ) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
        """Parse ``trusted_proxies`` into address networks, skipping invalid entries.

        A typo in one CIDR must not take the whole service down, but it *does*
        silently drop that entry — which is the safe direction, because an
        untrusted (empty) list means the X-Forwarded-For header is ignored.
        """
        networks = []
        for cidr in self.trusted_proxies.split(","):
            cidr = cidr.strip()
            if not cidr:
                continue
            try:
                networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                continue
        return tuple(networks)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
