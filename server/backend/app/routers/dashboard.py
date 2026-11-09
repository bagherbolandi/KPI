# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models
from ..security import get_current_user
from ..jalali import label, month_name, today
from ..settings_util import get_setting

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

STATUS_KEYS = ["green", "yellow", "red"]


def _latest_entry_map(db, year, approved_only=True):
    """For each KPI return its most recent entry within `year` (<= given)."""
    q = db.query(models.KPIEntry).filter(models.KPIEntry.year == year)
    if approved_only:
        q = q.filter(models.KPIEntry.workflow_state.in_(["approved", "qc_reviewed", "submitted"]))
    latest = {}
    for e in q.order_by(models.KPIEntry.month.asc()).all():
        if e.actual is None:
            continue
        latest[e.kpi_id] = e   # later months overwrite -> keeps most recent
    return latest


@router.get("/overview")
def overview(year: int = Query(None), company: int | None = None,
             db: Session = Depends(get_db), user=Depends(get_current_user)):
    year = year or int(get_setting(db, "current_year", today()["year"]))
    kpis = db.query(models.KPI).filter(models.KPI.active == True).all()  # noqa
    if company:
        from ..effective import process_company_map, kpis_of_company
        kpis = kpis_of_company(kpis, company, process_company_map(db))
    latest = _latest_entry_map(db, year)

    counts = {"green": 0, "yellow": 0, "red": 0, "nodata": 0}
    ach_vals = []
    w_num = w_den = 0.0
    for k in kpis:
        e = latest.get(k.id)
        if not e or e.status is None:
            counts["nodata"] += 1
            continue
        counts[e.status] += 1
        if e.achievement is not None:
            ach_vals.append(e.achievement)
            w_num += e.achievement * (k.weight or 1)
            w_den += (k.weight or 1)
    avg = round(sum(ach_vals) / len(ach_vals) * 100, 1) if ach_vals else 0
    wavg = round(w_num / w_den * 100, 1) if w_den else 0
    total = len(kpis)
    return {
        "year": year, "year_label": label(year, today()["month"]).split(" ")[-1],
        "total": total, "counts": counts,
        "avg_achievement": avg, "weighted_achievement": wavg,
        "green_pct": round(counts["green"] / total * 100, 1) if total else 0,
        "org_name": get_setting(db, "org_name", ""),
        "measured": total - counts["nodata"],
    }


@router.get("/by-process")
def by_process(year: int = Query(None), company: int | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    year = year or int(get_setting(db, "current_year", today()["year"]))
    procs = (db.query(models.OrgUnit).filter(models.OrgUnit.level == "process")
             .order_by(models.OrgUnit.order).all())
    if company:
        from ..effective import process_company_map
        pm = process_company_map(db)
        procs = [p for p in procs if pm.get(p.id) == company]
    latest = _latest_entry_map(db, year)
    kpis = db.query(models.KPI).all()
    by_proc = {}
    for k in kpis:
        by_proc.setdefault(k.process_id, []).append(k)
    out = []
    for p in procs:
        ks = by_proc.get(p.id, [])
        c = {"green": 0, "yellow": 0, "red": 0, "nodata": 0}
        achs = []
        for k in ks:
            e = latest.get(k.id)
            if not e or e.status is None:
                c["nodata"] += 1
            else:
                c[e.status] += 1
                if e.achievement is not None:
                    achs.append(e.achievement)
        avg = round(sum(achs) / len(achs) * 100, 1) if achs else 0
        out.append({"process_id": p.id, "code": p.code, "name": p.name,
                    "total": len(ks), "counts": c, "avg_achievement": avg,
                    "critical": c["red"]})
    out.sort(key=lambda x: x["avg_achievement"], reverse=True)
    return out


@router.get("/trend")
def trend(kpi_id: int = Query(None), process_id: int = Query(None),
          months: int = 12, company: int | None = None,
          db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return chronological achievement trend (last N periods) org/process/kpi-wide."""
    q = db.query(models.KPIEntry).join(models.KPI).filter(models.KPIEntry.actual != None)  # noqa
    if kpi_id:
        q = q.filter(models.KPIEntry.kpi_id == kpi_id)
    elif process_id:
        q = q.filter(models.KPI.process_id == process_id)
    elif user.role.code == "process_owner" and user.process_id:
        q = q.filter(models.KPI.process_id == user.process_id)
    elif company:
        from ..effective import process_company_map
        pm = process_company_map(db)
        allowed = [pid for pid, cid in pm.items() if cid == company]
        q = q.filter(models.KPI.process_id.in_(allowed or [-1]))
    rows = q.all()
    bucket = {}   # (year,month) -> list
    actuals = {}
    for e in rows:
        key = (e.year, e.month)
        if e.achievement is not None:
            bucket.setdefault(key, []).append(e.achievement)
        if kpi_id and e.actual is not None:
            actuals[key] = e.actual
    periods = sorted(bucket.keys())[-months:]
    labels = [label(y, m) for (y, m) in periods]
    ach = [round(sum(bucket[p]) / len(bucket[p]) * 100, 1) for p in periods]
    result = {"labels": labels, "achievement": ach}
    if kpi_id:
        k = db.get(models.KPI, kpi_id)
        result["actual"] = [actuals.get(p) for p in periods]
        result["target"] = [k.target for _ in periods]
        result["uom"] = k.uom
        result["name"] = k.name
    return result


@router.get("/pareto")
def pareto(year: int = Query(None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Pareto of critical (red) KPIs by process, weighted by KPI weight."""
    year = year or int(get_setting(db, "current_year", today()["year"]))
    latest = _latest_entry_map(db, year)
    kpis = db.query(models.KPI).all()
    proc_names = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    weighted = {}
    for k in kpis:
        e = latest.get(k.id)
        if e and e.status == "red":
            weighted[k.process_id] = weighted.get(k.process_id, 0) + (k.weight or 1)
    items = [{"name": proc_names.get(pid, "?"), "value": v} for pid, v in weighted.items()]
    items.sort(key=lambda x: x["value"], reverse=True)
    total = sum(i["value"] for i in items) or 1
    cum = 0
    for i in items:
        cum += i["value"]
        i["cum_pct"] = round(cum / total * 100, 1)
    return items


@router.get("/strategic")
def strategic(year: int = Query(None), company: int | None = None,
              db: Session = Depends(get_db), user=Depends(get_current_user)):
    year = year or int(get_setting(db, "current_year", today()["year"]))
    latest = _latest_entry_map(db, year)
    ks = db.query(models.KPI).filter(models.KPI.is_strategic == True).all()  # noqa
    if company:
        from ..effective import process_company_map, kpis_of_company
        ks = kpis_of_company(ks, company, process_company_map(db))
    proc_names = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    out = []
    for k in ks:
        e = latest.get(k.id)
        out.append({"code": k.code, "name": k.name, "process": proc_names.get(k.process_id),
                    "uom": k.uom, "target": k.target,
                    "actual": e.actual if e else None,
                    "achievement": round(e.achievement * 100, 1) if e and e.achievement is not None else None,
                    "status": e.status if e else None,
                    "period": label(e.year, e.month) if e else None})
    return out


@router.get("/critical")
def critical(year: int = Query(None), company: int | None = None,
             db: Session = Depends(get_db), user=Depends(get_current_user)):
    year = year or int(get_setting(db, "current_year", today()["year"]))
    latest = _latest_entry_map(db, year)
    ks = db.query(models.KPI).all()
    if company:
        from ..effective import process_company_map, kpis_of_company
        ks = kpis_of_company(ks, company, process_company_map(db))
    proc_names = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    out = []
    for k in ks:
        e = latest.get(k.id)
        if e and e.status == "red":
            out.append({"code": k.code, "name": k.name, "process": proc_names.get(k.process_id),
                        "uom": k.uom, "target": k.target, "actual": e.actual,
                        "achievement": round(e.achievement * 100, 1) if e.achievement is not None else None,
                        "period": label(e.year, e.month),
                        "cause": e.deviation_cause, "action": e.corrective_action,
                        "importance": k.importance})
    out.sort(key=lambda x: (x["achievement"] is not None, x["achievement"] or 0))
    return out


# ==================================================================== #
#  Offline-parity additions: top/bottom ranking (uncapped achievement), #
#  division radar, optional company scoping                            #
# ==================================================================== #
from ..effective import process_company_map, kpis_of_company, is_mgt, mgt_actual  # noqa: E402
from ..calc import achievement as _ach  # noqa: E402


def _uncapped(actual, target, direction):
    """Raw achievement ratio without the 100% cap (offline top/bottom charts)."""
    if actual is None:
        return None
    a, t = float(actual), float(target)
    if direction == "up":
        if t > 0:
            r = a / t
        elif t < 0:
            r = 1 + (a - t) / abs(t)
        else:
            r = 1.0 if a >= 0 else 0.0
    else:
        if t > 0:
            r = t / a if a > 0 else 1.0
        elif t < 0:
            r = 1 + (t - a) / abs(t)
        else:
            r = 1.0 if a <= 0 else 0.0
    return round(r * 100, 1)


@router.get("/top")
def top_bottom(year: int = Query(None), company: int | None = None,
               limit: int = 10, db: Session = Depends(get_db),
               user=Depends(get_current_user)):
    """برترین/ضعیف‌ترین شاخص‌ها — تحقق واقعی بدون سقف ۱۰۰٪."""
    year = year or int(get_setting(db, "current_year", today()["year"]))
    proc_company = process_company_map(db)
    kpis = kpis_of_company(db.query(models.KPI).filter(models.KPI.active == True).all(),  # noqa
                           company, proc_company)
    latest = _latest_entry_map(db, year)
    out = []
    for k in kpis:
        if is_mgt(k):
            act = mgt_actual(db, year, 12, proc_company=proc_company, company_id=company)
        else:
            e = latest.get(k.id)
            act = e.actual if e else None
        if act is None:
            continue
        unc = _uncapped(act, k.target, k.direction)
        if unc is None:
            continue
        out.append({"code": k.code, "name": k.name, "value": unc,
                    "actual": act, "target": k.target})
    out.sort(key=lambda x: -x["value"])
    return {"year": year,
            "top": out[:limit],
            "bottom": list(reversed(out[-limit:])) if out else []}


@router.get("/radar")
def radar(year: int = Query(None), company: int | None = None,
          db: Session = Depends(get_db), user=Depends(get_current_user)):
    """نمودار راداری معاونت‌ها — میانگین تحقق هر معاونت."""
    year = year or int(get_setting(db, "current_year", today()["year"]))
    proc_company = process_company_map(db)
    kpis = kpis_of_company(db.query(models.KPI).filter(models.KPI.active == True).all(),  # noqa
                           company, proc_company)
    latest = _latest_entry_map(db, year)
    units = {u.id: u for u in db.query(models.OrgUnit).all()}
    buckets = {}
    for k in kpis:
        proc = units.get(k.process_id)
        div = units.get(proc.parent_id) if proc and proc.parent_id else None
        if not div:
            continue
        e = latest.get(k.id)
        if not e or e.achievement is None:
            continue
        buckets.setdefault(div.name, []).append(e.achievement)
    items = [{"name": name, "value": round(sum(v) / len(v) * 100, 1), "n": len(v)}
             for name, v in buckets.items()]
    items.sort(key=lambda x: -x["value"])
    return {"year": year, "items": items}
