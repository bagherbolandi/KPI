# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from . import models
from .config import DEFAULT_TH_GREEN, DEFAULT_TH_YELLOW


def get_setting(db: Session, key: str, default=None):
    s = db.get(models.Setting, key)
    return s.value if s else default


def set_setting(db: Session, key: str, value: str):
    s = db.get(models.Setting, key)
    if s:
        s.value = value
    else:
        db.add(models.Setting(key=key, value=value))


def get_thresholds(db: Session):
    try:
        g = float(get_setting(db, "th_green", DEFAULT_TH_GREEN))
        y = float(get_setting(db, "th_yellow", DEFAULT_TH_YELLOW))
    except (TypeError, ValueError):
        g, y = DEFAULT_TH_GREEN, DEFAULT_TH_YELLOW
    return g, y
