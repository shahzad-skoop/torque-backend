from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def get_current_subject(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    settings = get_settings()

    if not settings.api_require_auth:
        return "local-dev"

    if settings.dev_bypass_auth and settings.app_env != "production":
        return "local-dev"

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # TODO: Replace with real token verification contract from auth service.
    return authorization.removeprefix("Bearer ").strip() or "authenticated-user"
