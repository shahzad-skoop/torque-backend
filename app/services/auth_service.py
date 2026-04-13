from __future__ import annotations

import json
import secrets

import requests

from app.core.config import get_settings
from app.schemas.auth import LoginRequest, SignupRequest

settings = get_settings()


class AuthServiceError(Exception):
    pass


def _prefix_value(prefix: str, value: str) -> str:
    if not value:
        return value
    prefix = (prefix or "").strip()
    if not prefix:
        return value
    return f"{prefix} {value}"


def _build_headers() -> dict[str, str]:
    return {
        "Authorization": _prefix_value(settings.auth_authorization_prefix, settings.auth_app_secret),
        "Client-Secret": _prefix_value(settings.auth_client_secret_prefix, settings.auth_client_secret),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def login_user(payload: LoginRequest) -> dict:
    if settings.auth_mock_mode:
        return {
            "token": f"mock_{secrets.token_urlsafe(24)}",
            "token_type": "Bearer",
            "expires_in": 86400,
        }

    if not settings.auth_service_base_url:
        raise AuthServiceError("AUTH_SERVICE_BASE_URL is not configured")

    response = requests.post(
        f"{settings.auth_service_base_url.rstrip('/')}/login",
        headers=_build_headers(),
        json=payload.model_dump(),
        timeout=30,
    )
    if response.status_code >= 400:
        raise AuthServiceError(f"Auth login failed: {response.status_code} {response.text}")
    return response.json()


def signup_user(payload: SignupRequest) -> dict:
    if settings.auth_mock_mode:
        return {
            "token": f"mock_{secrets.token_urlsafe(24)}",
            "token_type": "Bearer",
            "expires_in": 86400,
        }

    if not settings.auth_service_base_url:
        raise AuthServiceError("AUTH_SERVICE_BASE_URL is not configured")

    body = {
        "email": payload.email,
        "password": payload.password,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "environment": payload.environment or settings.auth_environment,
        "meta_data": json.dumps(payload.meta_data or {"role": "user"}),
    }

    response = requests.post(
        f"{settings.auth_service_base_url.rstrip('/')}/sign-up",
        headers=_build_headers(),
        json=body,
        timeout=30,
    )
    if response.status_code >= 400:
        raise AuthServiceError(f"Auth signup failed: {response.status_code} {response.text}")
    return response.json()
