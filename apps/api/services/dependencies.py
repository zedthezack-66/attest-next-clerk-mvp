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
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = db.get(User, claims["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    set_tenant(db, str(user.tenant_id))
    return user

