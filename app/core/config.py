from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Torque Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    database_url: str = "sqlite:///./torque.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket: str = "torque-artifacts"
    minio_secure: bool = False

    auth_service_base_url: str = ""
    auth_app_secret: str = ""
    auth_client_secret: str = ""
    auth_authorization_prefix: str = "Bearer"
    auth_client_secret_prefix: str = ""
    auth_environment: str = "production"
    auth_mock_mode: bool = True

    api_require_auth: bool = False
    dev_bypass_auth: bool = True

    simulate_analysis: bool = True
    simulate_analysis_delay_seconds: int = 1

    celery_task_always_eager: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
