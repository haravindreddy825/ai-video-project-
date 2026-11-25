import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

auth_router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    auth_required: bool


def _sign_token(username: str, ttl_sec: int = 86400) -> str:
    payload = {"sub": username, "exp": int(time.time()) + ttl_sec}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    sig = hmac.new(
        settings.AUTH_SECRET.encode("utf-8"), raw.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{raw}.{sig}"


def verify_bearer_token(token: str) -> Optional[str]:
    try:
        raw, sig = token.split(".", 1)
        expected = hmac.new(
            settings.AUTH_SECRET.encode("utf-8"), raw.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return str(payload.get("sub"))
    except Exception:
        return None


def require_auth(authorization: Optional[str] = Header(default=None)) -> str:
    if not settings.AUTH_REQUIRED:
        if authorization and authorization.lower().startswith("bearer "):
            user = verify_bearer_token(authorization.split(" ", 1)[1].strip())
            if user:
                return user
        return settings.STUDIO_USERNAME

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = verify_bearer_token(authorization.split(" ", 1)[1].strip())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return user


@auth_router.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(payload: LoginRequest) -> TokenResponse:
    if not (
        hmac.compare_digest(payload.username, settings.STUDIO_USERNAME)
        and hmac.compare_digest(payload.password, settings.STUDIO_PASSWORD)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid studio credentials",
        )
    token = _sign_token(payload.username)
    return TokenResponse(
        access_token=token,
        username=payload.username,
        auth_required=settings.AUTH_REQUIRED,
    )


@auth_router.get("/api/v1/auth/me", tags=["Auth"])
async def get_auth_status(user: str = Depends(require_auth)) -> dict[str, object]:
    return {
        "authenticated": True,
        "username": user,
        "auth_required": settings.AUTH_REQUIRED,
    }
