from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    environment: str = "production"
    meta_data: dict | None = None


class AuthTokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int = 86400
