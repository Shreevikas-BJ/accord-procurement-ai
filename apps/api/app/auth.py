import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import AuthSession, User


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f"{salt}:{digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split(":")
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, digest)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("procurement_session", "")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if not session or session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(401, "Please sign in to your procurement workspace.")
    user = db.get(User, session.user_id)
    if not user or not user.active or user.organization_id != session.organization_id:
        raise HTTPException(401, "Account is unavailable.")
    return user


def buyer(user: User = Depends(current_user)) -> User:
    if user.role not in ("Admin", "Buyer"):
        raise HTTPException(403, "A Buyer or Admin role is required for this action.")
    return user


def admin(user: User = Depends(current_user)) -> User:
    if user.role != "Admin":
        raise HTTPException(403, "An Admin role is required for this action.")
    return user


def secure_cookie():
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"
