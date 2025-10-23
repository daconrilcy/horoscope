"""
Module d'authentification et de gestion des tokens.

Ce module fournit les fonctions pour le hachage des mots de passe, la création et validation des
tokens JWT, et la gestion des données d'authentification.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class TokenData(BaseModel):
    """Données contenues dans un token JWT."""

    sub: str
    email: EmailStr
    entitlements: list[str] = []


def hash_password(p: str) -> str:
    """Hache un mot de passe en utilisant PBKDF2."""
    return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
    """Vérifie un mot de passe contre son hash."""
    return pwd_context.verify(p, h)


def create_access_token(
    secret: str, alg: str, expires_min: int, payload: dict[str, Any]
) -> str:
    """Crée un token JWT d'accès avec expiration."""
    to_encode = payload.copy()
    expire = datetime.now(UTC) + timedelta(minutes=expires_min)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret, algorithm=alg).decode("utf-8")


def decode_token(token: str, secret: str, alg: str) -> TokenData | None:
    """Décode et valide un token JWT."""
    try:
        data = jwt.decode(token, secret, algorithms=[alg])
        return TokenData(**data)
    except InvalidTokenError:
        return None
