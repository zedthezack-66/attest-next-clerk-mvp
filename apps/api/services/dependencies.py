from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from apps.api.models.database import get_db, set_tenant
from apps.api.models.entities import User
from apps.api.services.auth import decode_token


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        claims = decode_token(authorization.removeprefix("Bearer "))
        user_id = UUID(claims["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    set_tenant(db, str(user.tenant_id))
    return user



RECRUITER_ROLES = {"admin", "recruiter", "manager"}


def require_recruiter(user: User = Depends(current_user)) -> User:
    if user.role not in RECRUITER_ROLES or not user.is_active:
        raise HTTPException(status_code=403, detail="Recruiter access required")
    return user
