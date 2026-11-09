# -*- coding: utf-8 -*-
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..schemas import UserIn, UserOut
from ..security import require_roles, hash_password
from ..routers.auth import user_to_out, password_policy_error
from ..permissions import VIEW_KEYS, parse_permissions
from ..audit import log

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    return [user_to_out(u) for u in db.query(models.User).order_by(models.User.id).all()]


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), user=Depends(require_roles("admin", "quality"))):
    return [{"code": r.code, "name_fa": r.name_fa, "name_en": r.name_en,
             "description": r.description} for r in db.query(models.Role).all()]


@router.get("/views")
def list_views(user=Depends(require_roles("admin"))):
    """View keys + labels for the per-user permission editor (offline parity)."""
    from ..permissions import VIEW_LABELS, ROLE_PERMS
    return {"views": [{"key": k, "label": VIEW_LABELS[k]} for k in VIEW_KEYS],
            "role_defaults": ROLE_PERMS}


@router.post("", response_model=UserOut)
def create_user(body: UserIn, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(400, "نام کاربری تکراری است")
    role = db.query(models.Role).filter(models.Role.code == body.role_code).first()
    if not role:
        raise HTTPException(400, "نقش نامعتبر")
    pw = body.password or "Passw0rd!"
    if body.password:
        err = password_policy_error(pw)
        if err:
            raise HTTPException(400, err)
    perms = json.dumps(parse_permissions(body.permissions)) if body.permissions else None
    u = models.User(username=body.username, full_name=body.full_name, email=body.email,
                    hashed_password=hash_password(pw),
                    role_id=role.id, process_id=body.process_id, is_active=body.is_active,
                    permissions=perms, must_change=bool(body.must_change))
    db.add(u); db.flush()
    log(db, user, "user", u.id, "create", new_value=body.username)
    db.commit()
    return user_to_out(u)


@router.put("/{uid}", response_model=UserOut)
def update_user(uid: int, body: UserIn, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    u = db.get(models.User, uid)
    if not u:
        raise HTTPException(404, "یافت نشد")
    role = db.query(models.Role).filter(models.Role.code == body.role_code).first()
    u.full_name = body.full_name; u.email = body.email
    u.role_id = role.id; u.process_id = body.process_id; u.is_active = body.is_active
    u.must_change = bool(body.must_change)
    # permissions: null -> keep as-is (role default when never customized);
    # explicit list -> store the override
    if body.permissions is not None:
        u.permissions = json.dumps(parse_permissions(body.permissions))
    if body.password:
        err = password_policy_error(body.password)
        if err:
            raise HTTPException(400, err)
        u.hashed_password = hash_password(body.password)
        u.must_change = bool(body.must_change)
    log(db, user, "user", u.id, "update", new_value=body.username)
    db.commit()
    return user_to_out(u)


@router.delete("/{uid}")
def delete_user(uid: int, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    u = db.get(models.User, uid)
    if not u:
        raise HTTPException(404, "یافت نشد")
    if u.username == "admin":
        raise HTTPException(400, "حذف مدیر سیستم اصلی مجاز نیست")
    log(db, user, "user", u.id, "delete", old_value=u.username)
    db.delete(u); db.commit()
    return {"ok": True}
