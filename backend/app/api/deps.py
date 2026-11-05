"""Authentication (JWT) and role-based access control for the multi-persona UI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings
from app.storage.relational import User, session

ROLES = ("hr_admin", "hiring_manager", "employee", "leadership")
_bearer = HTTPBearer(auto_error=False)


class Principal(BaseModel):
    username: str
    display_name: str
    role: str
    employee_id: str | None = None
    title: str = ""

    @property
    def mcp_user(self) -> str:
        return self.employee_id if self.role == "employee" and self.employee_id else self.username


def authenticate(username: str, password: str) -> Principal | None:
    with session() as s:
        u = s.get(User, username)
        if not u or not bcrypt.checkpw(password.encode(), u.password_hash.encode()):
            return None
        return Principal(username=u.username, display_name=u.display_name, role=u.role, employee_id=u.employee_id, title=u.title)


def issue_token(p: Principal) -> str:
    s = get_settings()
    payload = {**p.model_dump(), "sub": p.username, "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_ttl_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Principal:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    return Principal(**{k: data.get(k) for k in Principal.model_fields})


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return decode_token(creds.credentials)


def require_roles(*roles: str):
    def dep(user: Principal = Depends(current_user)) -> Principal:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user
    return dep
