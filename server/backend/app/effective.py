# -*- coding: utf-8 -*-
"""Effective-value helpers ported from the offline app.

- is_due():      frequency-based due months (monthly/quarterly/semiannual/annual/event)
- is_mgt():      management KPI (process code MGT) is derived, never entered by hand
- mgt_actual():  running YTD mean of all other KPIs' achievements (percent)
- company maps:  process -> company ancestry for multi-company scoping
"""
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .calc import achievement


def is_due(frequency: str, month: int) -> bool:
    f = frequency or "monthly"
    if f == "monthly":
        return True
    if f == "quarterly":
        return month % 3 == 0
    if f == "semiannual":
        return month % 6 == 0
    if f == "annual":
        return month == 12
    return True  # event / per_ecn


def period_hint(frequency: str) -> str:
    return {
        "quarterly": "فصلی (پایان هر فصل)",
        "semiannual": "شش‌ماهه (شهریور/اسفند)",
        "annual": "سالانه (اسفند)",
        "event": "به‌ازای هر رویداد",
    }.get(frequency or "monthly", "ماهانه")


def is_mgt(kpi: models.KPI) -> bool:
    try:
        return bool(kpi.process and kpi.process.code == "MGT")
    except Exception:
        return False


def process_company_map(db: Session) -> dict:
    """process_id -> company_id (process -> division -> company)."""
    units = db.query(models.OrgUnit).all()
    by_id = {u.id: u for u in units}
    out = {}
    for u in units:
        if u.level != "process":
            continue
        div = by_id.get(u.parent_id)
        comp = by_id.get(div.parent_id) if div and div.parent_id else None
        if comp and comp.level == "company":
            out[u.id] = comp.id
    return out


def kpis_of_company(kpis, company_id: Optional[int], proc_company: dict):
    if not company_id:
        return kpis
    return [k for k in kpis if proc_company.get(k.process_id) == company_id]


def mgt_actual(db: Session, year: int, month: int,
               approved_only: bool = False,
               proc_company: Optional[dict] = None,
               company_id: Optional[int] = None) -> Optional[float]:
    """Offline getMgtDerivedActual: YTD mean of every other KPI's achievement
    for entries up to and including `month`, returned in percent (0..100+)."""
    q = (db.query(models.KPIEntry, models.KPI)
         .join(models.KPI)
         .filter(models.KPIEntry.year == year,
                 models.KPIEntry.month <= month,
                 models.KPIEntry.actual != None))  # noqa: E711
    if approved_only:
        q = q.filter(models.KPIEntry.workflow_state == "approved")
    rows = q.all()
    total = 0.0
    n = 0
    for e, k in rows:
        if is_mgt(k) or not k.active:
            continue
        if company_id and proc_company and proc_company.get(k.process_id) != company_id:
            continue
        a = achievement(e.actual, k.target, k.direction)
        if a is not None:
            total += a
            n += 1
    if n == 0:
        return None
    return round((total / n) * 10000) / 100


def effective_actual(db: Session, kpi: models.KPI, year: int, month: int,
                     approved_only: bool = False) -> Optional[float]:
    if is_mgt(kpi):
        return mgt_actual(db, year, month, approved_only=approved_only)
    e = (db.query(models.KPIEntry)
         .filter_by(kpi_id=kpi.id, year=year, month=month).first())
    if not e or e.actual is None:
        return None
    if approved_only and e.workflow_state != "approved":
        return None
    return e.actual
