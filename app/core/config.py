"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5442/charmelio"

    # MinIO / S3
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_UPLOADS: str = "uploads"
    S3_BUCKET_EXTRACTIONS: str = "extractions"

    # Temporal
    TEMPORAL_ADDRESS: str = "temporal:7233"
    TEMPORAL_NAMESPACE: str = "default"
    WORKER_TASK_QUEUE: str = "extraction-queue"

    # OpenAI
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o-mini"

    # Application
    APP_NAME: str = "Charmelio - Contract Clause Extractor"
    APP_ENV: str = "dev"
    MAX_FILE_SIZE_MB: int = 25

    # PDF Parsing
    PDF_MAX_FILE_SIZE_MB: int = 25
    PDF_MAX_PAGES: int = 100

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


# Global settings instance
settings = Settings()
