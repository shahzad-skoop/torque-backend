from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import get_settings
from app.schemas.auth import AuthTokenResponse, LoginRequest, SignupRequest
from app.services.auth_service import AuthServiceError, login_user, signup_user

router = APIRouter()


def _set_session_cookie(response: Response, token: str, expires_in: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key="torque_session",
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=expires_in,
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, response: Response):
    try:
        result = login_user(payload)
        token = result.get("token", "")
        if token:
            _set_session_cookie(response, token, int(result.get("expires_in", 86400)))
        return result
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/signup", response_model=AuthTokenResponse)
def signup(payload: SignupRequest, response: Response):
    try:
        result = signup_user(payload)
        token = result.get("token", "")
        if token:
            _set_session_cookie(response, token, int(result.get("expires_in", 86400)))
        return result
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
