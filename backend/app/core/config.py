from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Azmark API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://azmark:azmark@localhost:5432/azmark"

    secret_key: str = "dev-secret-change-me-please-32bytes-minimum"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: str = "http://localhost:3000"

    aerodatabox_base_url: str = "https://aerodatabox.p.rapidapi.com"
    aerodatabox_host: str = "aerodatabox.p.rapidapi.com"

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
