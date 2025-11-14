from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres
    POSTGRES_USER: str = "raypp"
    POSTGRES_PASSWORD: str = "raypp_password"
    POSTGRES_DB: str = "raypp_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # Cache settings
    CACHE_PREFIX: str = "ask"
    CACHE_TTL_SECONDS: int = 3600

    # Qdrant (vector DB)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None

    # Media
    MEDIA_ROOT: str = "media"

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Pydantic v2 settings: ignore extra env vars to avoid "extra_forbidden" errors
    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "case_sensitive": True,
    }

    @property
    def qdrant_url(self) -> str:
        if self.QDRANT_URL:
            return self.QDRANT_URL
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"


settings = Settings()
