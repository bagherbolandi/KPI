# -*- coding: utf-8 -*-
import re
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..config import SECRET_KEY, ALGORITHM
from ..security import (verify_password, create_access_token, get_current_user,
                        hash_password)
from ..schemas import (LoginResp, UserOut, ChangePasswordIn, AdminRecoveryIn,
                       CompleteSetupIn)
from ..permissions import effective_permissions
from ..audit import log
from ..settings_util import get_setting

router = APIRouter(prefix="/api/auth", tags=["auth"])

# offline parity: MAX_LOGIN_ATTEMPTS = 5, LOCK_MS = 5 minutes
MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 5

DEFAULT_PASSWORDS = {"Passw0rd!", "password", "admin123", "123456", "kpi12345"}


def user_to_out(u: models.User) -> UserOut:
    return UserOut(
        id=u.id, username=u.username, full_name=u.full_name, email=u.email,
        role_code=u.role.code, role_name=u.role.name_fa,
        process_id=u.process_id, process_name=u.process.name if u.process else None,
        is_active=u.is_active,
        permissions=effective_permissions(u),
        must_change=bool(u.must_change),
    )


# ------------------------------------------------- lockout (offline parity)
def _lock_row(db: Session, username: str) -> models.LoginLock | None:
    return db.get(models.LoginLock, username)


def _locked_until(row: models.LoginLock | None):
    if row and row.lock_until and row.lock_until > datetime.utcnow():
        return row.lock_until
    return None


def _record_failure(db: Session, username: str) -> None:
    row = _lock_row(db, username)
    if not row:
        row = models.LoginLock(username=username, attempts=0)
        db.add(row)
    row.attempts = (row.attempts or 0) + 1
    row.updated_at = datetime.utcnow()
    if row.attempts >= MAX_LOGIN_ATTEMPTS:
        row.lock_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
        row.attempts = 0
    db.commit()


def _clear_lock(db: Session, username: str) -> None:
    row = _lock_row(db, username)
    if row:
        row.attempts = 0
        row.lock_until = None
        db.commit()


def password_policy_error(p: str) -> str | None:
    """Offline pwWeak: at least 8 chars, letters AND digits; block defaults."""
    if len(p) < 8:
        return "رمز عبور باید حداقل ۸ کاراکتر باشد"
    if not re.search(r"[A-Za-z]", p) or not re.search(r"\d", p):
        return "رمز عبور باید شامل حرف و عدد باشد"
    if p in DEFAULT_PASSWORDS:
        return "این رمز مجاز نیست؛ یک رمز جدید انتخاب کنید"
    return None


@router.post("/login", response_model=LoginResp)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    row = _lock_row(db, form.username)
    until = _locked_until(row)
    if until:
        sec = int((until - datetime.utcnow()).total_seconds()) + 1
        raise HTTPException(status_code=400,
                            detail=f"حساب به دلیل تلاش‌های ناموفق قفل شده است. {sec} ثانیه دیگر تلاش کنید.")
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        _record_failure(db, form.username)
        # uniform message (offline wrongPwMsg) — do not leak which part was wrong
        raise HTTPException(status_code=400, detail="نام کاربری یا رمز عبور نادرست است")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="حساب کاربری غیرفعال است")
    _clear_lock(db, form.username)
    # offline parity: logging in with a shipped default password forces a change
    if form.password in DEFAULT_PASSWORDS and not user.must_change:
        user.must_change = True
        db.commit()
    elif user.must_change:
        db.commit()
    return LoginResp(access_token=create_access_token(user.username),
                     must_change=bool(user.must_change))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user_to_out(user)


@router.post("/change-password", response_model=LoginResp)
def change_password(body: ChangePasswordIn, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    """Change own password. When must_change is set the current password is
    still required only if the user knows it (they just logged in with it)."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="رمز عبور فعلی نادرست است")
    err = password_policy_error(body.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if verify_password(body.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="رمز جدید نباید با رمز فعلی یکسان باشد")
    user.hashed_password = hash_password(body.new_password)
    user.must_change = False
    log(db, user, "user", user.id, "update", field="password",
        new_value="***", reason="تغییر رمز عبور")
    db.commit()
    _clear_lock(db, user.username)
    return LoginResp(access_token=create_access_token(user.username), must_change=False)


@router.post("/admin-recovery")
def admin_recovery(body: AdminRecoveryIn, db: Session = Depends(get_db)):
    """Offline openAdminRecovery/doAdminRecovery: typing RESET clears the admin
    password (data and other users are kept) and returns a short-lived setup
    token used to set a brand-new password without knowing the old one."""
    # server hardening: recovery can be switched off in settings (default on,
    # because the offline app relies on it and this deployment is air-gapped)
    if str(get_setting(db, "recovery_enabled", "1")).strip() in ("0", "false", "no"):
        raise HTTPException(status_code=403,
                            detail="بازیابی رمز مدیر در این نصب غیرفعال است؛ با پشتیبان‌گیر پایگاه داده تماس بگیرید")
    if (body.confirm or "").strip() != "RESET":
        raise HTTPException(status_code=400,
                            detail="عبارت تأیید صحیح نیست؛ RESET را تایپ کنید")
    admin = db.query(models.User).filter(models.User.username == "admin").first()
    if not admin:
        raise HTTPException(status_code=404, detail="کاربر مدیر یافت نشد")
    # random unusable password + clear locks (offline clears LS_LOCK_KEY)
    admin.hashed_password = hash_password(secrets.token_urlsafe(24))
    admin.must_change = False
    admin.is_active = True
    db.query(models.LoginLock).delete()
    log(db, admin, "user", admin.id, "update", field="password",
        new_value="reset", reason="بازیابی دسترسی مدیر (RESET)")
    db.commit()
    token = jwt.encode({"sub": admin.username, "purpose": "setup",
                        "exp": datetime.utcnow() + timedelta(minutes=15)},
                       SECRET_KEY, algorithm=ALGORITHM)
    return {"setup_token": token, "username": admin.username}


@router.post("/complete-setup", response_model=LoginResp)
def complete_setup(body: CompleteSetupIn, db: Session = Depends(get_db)):
    """Set a new admin password after admin-recovery (offline attemptSetup)."""
    try:
        payload = jwt.decode(body.token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=400, detail="توکن نامعتبر یا منقضی است")
    if payload.get("purpose") != "setup":
        raise HTTPException(status_code=400, detail="توکن نامعتبر است")
    user = db.query(models.User).filter(models.User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    if body.password2 and body.password != body.password2:
        raise HTTPException(status_code=400, detail="رمز عبور و تکرار آن یکسان نیست")
    err = password_policy_error(body.password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    user.hashed_password = hash_password(body.password)
    user.must_change = False
    db.commit()
    _clear_lock(db, user.username)
    log(db, user, "user", user.id, "update", field="password",
        new_value="***", reason="راه‌اندازی رمز عبور پس از بازیابی")
    return LoginResp(access_token=create_access_token(user.username), must_change=False)
