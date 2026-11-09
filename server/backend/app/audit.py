# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from . import models


def log(db: Session, user, entity_type, entity_id, action,
        field="", old_value="", new_value="", reason=""):
    db.add(models.AuditLog(
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        entity_type=entity_type, entity_id=str(entity_id), action=action,
        field=str(field), old_value=str(old_value), new_value=str(new_value),
        reason=reason,
    ))
