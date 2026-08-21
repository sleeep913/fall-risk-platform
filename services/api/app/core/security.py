import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-user-password")


@dataclass(frozen=True)
class TokenClaims:
    subject: int
    token_type: Literal["access", "refresh"]
    jti: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    return password_hash.verify(password, encoded_password)


def create_token(
    *,
    subject: int,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    settings: Settings,
) -> tuple[str, TokenClaims]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())
    claims = {
        "sub": str(subject),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    encoded = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded, TokenClaims(subject, token_type, jti, expires_at)


def decode_token(
    token: str,
    *,
    expected_type: Literal["access", "refresh"],
    settings: Settings,
) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "jti", "iat", "exp"]},
        )
        if payload["type"] != expected_type:
            raise InvalidTokenError("Unexpected token type")
        return TokenClaims(
            subject=int(payload["sub"]),
            token_type=payload["type"],
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid or expired token") from exc


def token_fingerprint(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()

