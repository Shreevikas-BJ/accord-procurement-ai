import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from redis import Redis
from .db import get_db
from .models import User, AuthSession, Organization
from .schemas import Login, UserInput
from .auth import current_user, admin, verify_password, hash_password, token_hash, secure_cookie
from .common import audit
from .config import REDIS_URL

router = APIRouter()


def public_user(user, db):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "organization_id": user.organization_id,
        "organization": db.get(Organization, user.organization_id).name,
    }


@router.post("/auth/login")
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        redis = Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        key = "login:" + token_hash((request.client.host if request.client else "") + payload.email.lower())
        attempts = redis.incr(key)
        if attempts == 1:
            redis.expire(key, 300)
        if attempts > 20:
            raise HTTPException(429, "Too many sign-in attempts. Try again in five minutes.")
    except HTTPException:
        raise
    except Exception:
        # Credential hashing and generic errors remain active if Redis is unavailable.
        pass
    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            organization_id=user.organization_id,
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
    )
    audit(db, user.organization_id, user.id, "SIGNED_IN", "user", user.id)
    db.commit()
    response.set_cookie(
        "procurement_session", token, httponly=True, secure=secure_cookie(), samesite="strict", max_age=43200, path="/"
    )
    return public_user(user, db)


@router.get("/auth/me")
def me(user=Depends(current_user), db: Session = Depends(get_db)):
    return public_user(user, db)


@router.post("/auth/logout")
def logout(request: Request, response: Response, user=Depends(current_user), db: Session = Depends(get_db)):
    db.execute(
        delete(AuthSession).where(
            AuthSession.organization_id == user.organization_id,
            AuthSession.token_hash == token_hash(request.cookies.get("procurement_session", "")),
        )
    )
    db.commit()
    response.delete_cookie("procurement_session", path="/")
    return {"message": "Signed out"}


@router.get("/users")
def users(user=Depends(admin), db: Session = Depends(get_db)):
    return [public_user(u, db) for u in db.scalars(select(User).where(User.organization_id == user.organization_id))]


@router.post("/users", status_code=201)
def create_user(payload: UserInput, user=Depends(admin), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Email is unavailable.")
    new = User(
        organization_id=user.organization_id,
        email=payload.email.lower(),
        name=payload.name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(new)
    db.flush()
    audit(db, user.organization_id, user.id, "USER_CREATED", "user", new.id, new={"email": new.email, "role": new.role})
    db.commit()
    return public_user(new, db)
