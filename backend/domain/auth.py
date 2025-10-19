from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class TokenData(BaseModel):
    sub: str
    email: EmailStr
    entitlements: list[str] = []


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)


def create_access_token(secret: str, alg: str, expires_min: int, payload: dict[str, Any]) -> str:
    to_encode = payload.copy()
    expire = datetime.now(UTC) + timedelta(minutes=expires_min)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret, algorithm=alg)


def decode_token(token: str, secret: str, alg: str) -> TokenData | None:
    try:
        data = jwt.decode(token, secret, algorithms=[alg])
        return TokenData(**data)
    except InvalidTokenError:
        return None
