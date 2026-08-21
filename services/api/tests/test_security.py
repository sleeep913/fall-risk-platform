from datetime import timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_round_trip() -> None:
    encoded = hash_password("a-strong-test-password")
    assert encoded != "a-strong-test-password"
    assert verify_password("a-strong-test-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_token_type_is_enforced() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
    )
    token, _ = create_token(
        subject=7,
        token_type="refresh",
        expires_delta=timedelta(minutes=5),
        settings=settings,
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, expected_type="access", settings=settings)


def test_production_rejects_development_secret() -> None:
    with pytest.raises(ValueError, match="unique JWT_SECRET"):
        Settings(_env_file=None, app_env="production")
