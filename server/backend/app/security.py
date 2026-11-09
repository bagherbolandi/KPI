# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session

from .database import get_db
from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8")[:72], h.encode("utf-8"))
    except Exception:
        return False


def create_access_token(sub: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> models.User:
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="اعتبارسنجی ناموفق بود",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise cred_exc
    return user


def require_roles(*roles: str):
    """Dependency factory: allow only users whose role.code is in roles."""
    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role.code not in roles:
            raise HTTPException(status_code=403, detail="دسترسی غیرمجاز برای این عملیات")
        return user
    return checker
