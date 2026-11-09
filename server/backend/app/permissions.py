# -*- coding: utf-8 -*-
"""View permissions — offline ROLE_PERMS model applied to the server.

Default permission sets per role; a user may carry an explicit per-user
override (User.permissions JSON list), exactly like the offline app.
"""
import json

VIEW_KEYS = [
    "dashboard", "holding", "processes", "kpis", "strategy", "entry",
    "approvals", "master", "org", "companies", "reports", "settings",
    "users", "audit",
]

VIEW_LABELS = {
    "dashboard": "داشبورد مدیریتی",
    "holding": "داشبورد هلدینگ",
    "processes": "فرایندها",
    "kpis": "شاخص‌ها و روندها",
    "strategy": "اهداف و برنامه‌ها",
    "entry": "ورود اطلاعات",
    "approvals": "کارتابل تأیید",
    "master": "مدیریت شاخص‌ها",
    "org": "ساختار سازمانی",
    "companies": "شرکت‌های هلدینگ",
    "reports": "گزارش‌ها و خروجی",
    "settings": "تنظیمات",
    "users": "کاربران و نقش‌ها",
    "audit": "لاگ تغییرات",
}

# Offline defaults (ROLE_PERMS) mapped onto server pages, plus server-only pages.
ROLE_PERMS = {
    "admin": list(VIEW_KEYS),
    "quality": ["dashboard", "processes", "kpis", "strategy", "entry",
                "approvals", "org", "reports", "audit"],
    "executive": ["dashboard", "holding", "processes", "kpis", "strategy",
                  "org", "companies", "reports"],
    "process_owner": ["dashboard", "processes", "kpis", "strategy", "entry",
                      "approvals", "org"],
}


def parse_permissions(raw) -> list:
    """Accepts a JSON string (DB column) or an already-decoded list (API body)."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [v for v in raw if v in VIEW_KEYS]
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return [v for v in val if v in VIEW_KEYS]
    except (TypeError, ValueError):
        pass
    return []


def effective_permissions(user) -> list:
    """Explicit per-user override, else the role default."""
    explicit = parse_permissions(getattr(user, "permissions", None))
    if explicit:
        return explicit
    return list(ROLE_PERMS.get(user.role.code, []))


def can(user, view: str) -> bool:
    return view in effective_permissions(user)
