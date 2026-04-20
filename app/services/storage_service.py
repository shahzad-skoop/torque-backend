from __future__ import annotations

from minio import Minio

from app.core.config import get_settings


class StorageConfigurationError(RuntimeError):
    """Raised when MinIO/object-storage credentials are not configured correctly."""


def get_minio_client() -> Minio:
    """Build a MinIO client from settings.

    Always prefers the app-scoped access key / secret key. In non-production
    environments we fall back to the MinIO root credentials so local
    docker-compose flows keep working out of the box. In production we refuse
    to start if app credentials are missing — root credentials must never be
    used by the application runtime.
    """
    settings = get_settings()

    access_key = settings.minio_access_key
    secret_key = settings.minio_secret_key

    if not access_key or not secret_key:
        if settings.app_env.lower() == "production":
            raise StorageConfigurationError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in production. "
                "Do not use MinIO root credentials for application access."
            )
        access_key = access_key or settings.minio_root_user
        secret_key = secret_key or settings.minio_root_password

    return Minio(
        settings.minio_endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=settings.minio_secure,
    )
