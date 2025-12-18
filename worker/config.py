"""Worker configuration.

Environment-based configuration for the Temporal worker.
"""
import os


class WorkerSettings:
    """Worker configuration from environment variables."""

    def __init__(self):
        # Temporal configuration
        self.TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "temporal:7233")
        self.TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
        self.WORKER_TASK_QUEUE = os.getenv("WORKER_TASK_QUEUE", "extraction-queue")

        # Database configuration
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@postgres:5432/charmelio"
        )

        # MinIO/S3 configuration
        self.S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
        self.S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")

        # OpenAI configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

    def __repr__(self):
        return (
            f"WorkerSettings(temporal={self.TEMPORAL_ADDRESS}, "
            f"queue={self.WORKER_TASK_QUEUE}, "
            f"namespace={self.TEMPORAL_NAMESPACE})"
        )
