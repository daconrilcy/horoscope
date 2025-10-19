from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr

from backend.core.container import container
from backend.domain.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupPayload(BaseModel):
    email: EmailStr
    password: str
    entitlements: list[str] = []  # e.g., ["plus"]


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
def signup(p: SignupPayload):
    existing = container.user_repo.get_by_email(str(p.email))
    if existing:
        raise HTTPException(status_code=409, detail="email_exists")
    user = {
        "id": __import__("uuid").uuid4().hex,
        "email": str(p.email),
        "password_hash": hash_password(p.password),
        "entitlements": p.entitlements or [],
    }
    container.user_repo.save(user)
    return {"id": user["id"], "email": user["email"], "entitlements": user["entitlements"]}


@router.post("/login")
def login(p: LoginPayload):
    user = container.user_repo.get_by_email(str(p.email))
    if not user or not verify_password(p.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(
        secret=container.settings.JWT_SECRET,
        alg=container.settings.JWT_ALG,
        expires_min=container.settings.JWT_EXPIRES_MIN,
        payload={
            "sub": user["id"],
            "email": user["email"],
            "entitlements": user.get("entitlements", []),
        },
    )
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_token")
    token = authorization.split(" ", 1)[1]
    data = decode_token(token, container.settings.JWT_SECRET, container.settings.JWT_ALG)
    if not data:
        raise HTTPException(status_code=401, detail="invalid_token")
    user = container.user_repo.get_by_email(str(data.email))
    if not user:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user

