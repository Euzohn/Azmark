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

    cors_origins: str = "http://localhost:3000"

    aerodatabox_base_url: str = "https://aerodatabox.p.rapidapi.com"
    aerodatabox_host: str = "aerodatabox.p.rapidapi.com"
    aviationstack_base_url: str = "http://api.aviationstack.com/v1"

    # VariFlight (飞常准) Aviation MCP endpoint — see spec #66.
    variflight_mcp_url: str = "https://ai.variflight.com/servers/aviation/mcp"

    # SearchProvider (spec #37) — used for train schedules and travel lookups.
    search_provider: str = ""
    search_api_key: str = ""
    searxng_base_url: str = ""

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
