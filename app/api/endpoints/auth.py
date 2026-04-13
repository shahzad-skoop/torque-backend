from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.auth import AuthTokenResponse, LoginRequest, SignupRequest
from app.services.auth_service import AuthServiceError, login_user, signup_user

router = APIRouter()


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, response: Response):
    try:
        result = login_user(payload)
        token = result.get("token", "")
        if token:
            response.set_cookie(
                key="torque_session",
                value=token,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=int(result.get("expires_in", 86400)),
            )
        return result
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/signup", response_model=AuthTokenResponse)
def signup(payload: SignupRequest, response: Response):
    try:
        result = signup_user(payload)
        token = result.get("token", "")
        if token:
            response.set_cookie(
                key="torque_session",
                value=token,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=int(result.get("expires_in", 86400)),
            )
        return result
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
