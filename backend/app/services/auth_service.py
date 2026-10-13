import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import os
import secrets
from typing import Optional
from sqlalchemy.orm import Session

from app.models.auth_schemas import UserLoginRequest, UserRegisterRequest
from app.models.db_models import UserORM

logger = logging.getLogger("veritas.services.auth")

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "veritas-editorial-saas-secret-key-2026"
ALGORITHM = "HS256"
TOKEN_EXPIRY_DAYS = 7


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique cryptographic salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against PBKDF2 salt$hash format."""
    try:
        salt, key_hex = hashed_password.split("$", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100_000,
        )
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception as exc:
        logger.warning(f"Password verification error: {exc}")
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ""
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(user_id: int, username: str, expires_days: int = TOKEN_EXPIRY_DAYS) -> str:
    """Generate a standard HMAC-SHA256 signed JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    exp = int((datetime.now(timezone.utc) + timedelta(days=expires_days)).timestamp())
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": exp,
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }

    hdr_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    pay_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{hdr_b64}.{pay_b64}".encode("utf-8")

    sig = hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{hdr_b64}.{pay_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[dict]:
    """Validate and decode HMAC-SHA256 signed JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        hdr_b64, pay_b64, sig_b64 = parts

        msg = f"{hdr_b64}.{pay_b64}".encode("utf-8")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload = json.loads(_b64url_decode(pay_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp and exp < datetime.now(timezone.utc).timestamp():
            return None  # Expired

        return payload
    except Exception as exc:
        logger.debug(f"Failed to decode token: {exc}")
        return None


def register_user(db: Session, req: UserRegisterRequest) -> UserORM:
    """Register a new user account."""
    existing_username = db.query(UserORM).filter(UserORM.username == req.username).first()
    if existing_username:
        raise ValueError(f"Username '{req.username}' is already taken.")

    existing_email = db.query(UserORM).filter(UserORM.email == req.email).first()
    if existing_email:
        raise ValueError(f"An account with email '{req.email}' already exists.")

    user = UserORM(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, req: UserLoginRequest) -> Optional[UserORM]:
    """Authenticate user by username/email and password."""
    identifier = req.username_or_email.strip()
    user = (
        db.query(UserORM)
        .filter((UserORM.username == identifier) | (UserORM.email == identifier))
        .first()
    )
    if not user:
        return None

    if not verify_password(req.password, user.hashed_password):
        return None

    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[UserORM]:
    """Retrieve user by primary key ID."""
    return db.query(UserORM).filter(UserORM.id == user_id).first()
