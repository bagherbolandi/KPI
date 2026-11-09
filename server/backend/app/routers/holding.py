# -*- coding: utf-8 -*-
"""Holding dashboard + company management (offline 'داشبورد هلدینگ' and
'شرکت‌های هلدینگ' views)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..security import get_current_user, require_roles
from ..settings_util import get_setting, get_thresholds
from ..jalali import label, today
from ..effective import process_company_map, kpis_of_company, is_mgt, mgt_actual
from ..calc import achievement, status_from_achievement, status_band
from ..audit import log

router = APIRouter(prefix="/api", tags=["holding"])

STATUS_KEYS = ("green", "yellow", "red")


def _latest_map(db, year: int, approved_only: bool = False):
    q = db.query(models.KPIEntry).filter(models.KPIEntry.year == year,
                                          models.KPIEntry.actual != None)  # noqa: E711
    if approved_only:
        q = q.filter(models.KPIEntry.workflow_state == "approved")
    latest = {}
    for e in q.order_by(models.KPIEntry.month.asc()).all():
        latest[e.kpi_id] = e
    return latest


def _cur_month(db) -> int:
    """Current Jalali month (1..12) used as the cut-off for cumulative MGT KPIs."""
    from ..jalali import today
    m = int(today()["month"])
    return max(1, min(12, m))


def company_stats(db, year: int, company_id: int, proc_company: dict,
                  th_green: float, th_yellow: float) -> dict:
    units = db.query(models.OrgUnit).all()
    comp = next((u for u in units if u.id == company_id), None)
    kpis = kpis_of_company(db.query(models.KPI).filter(models.KPI.active == True).all(),  # noqa
                           company_id, proc_company)
    latest = _latest_map(db, year)
    counts = {k: 0 for k in STATUS_KEYS}
    counts["nodata"] = 0
    wsum = wach = 0.0
    measured = 0
    for k in kpis:
        if is_mgt(k):
            # cumulative MGT KPIs: evaluate through the current month (offline
            # uses the latest available period, not a fixed month 12)
            act = mgt_actual(db, year, _cur_month(db), proc_company=proc_company,
                             company_id=company_id)
            e = None
        else:
            e = latest.get(k.id)
            act = e.actual if e else None
        if act is None:
            counts["nodata"] += 1
            continue
        if k.calc_mode == "band":
            st = status_band(act, k.target, k.warning, k.critical, k.direction)
            ach = achievement(act, k.target, k.direction)
        else:
            tg = k.th_green if k.th_green is not None else th_green
            ty = k.th_yellow if k.th_yellow is not None else th_yellow
            ach = achievement(act, k.target, k.direction)
            st = status_from_achievement(ach, tg, ty)
        if st:
            counts[st] += 1
        else:
            counts["nodata"] += 1
        if ach is not None:
            measured += 1
            w = k.weight or 1
            wach += ach * w
            wsum += w
    avg = round(wach / wsum * 100, 1) if wsum else 0.0
    return {"id": company_id, "code": comp.code if comp else "", "name": comp.name if comp else "",
            "total": len(kpis), "measured": measured, "counts": counts,
            "avg_achievement": avg,
            "status": (max(STATUS_KEYS, key=lambda s: counts[s])
                       if any(counts[s] for s in STATUS_KEYS) else None)}


@router.get("/holding/overview")
def holding_overview(year: int = Query(None),
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    year = year or int(get_setting(db, "current_year", today()["year"]))
    th_g, th_y = get_thresholds(db)
    proc_company = process_company_map(db)
    companies = [u for u in db.query(models.OrgUnit).filter_by(level="company")
                 .order_by(models.OrgUnit.order).all()]
    rows = [company_stats(db, year, c.id, proc_company, th_g, th_y) for c in companies]
    rows.sort(key=lambda r: (-r["avg_achievement"], r["name"]))
    measured = [r for r in rows if r["measured"]]
    holding_avg = round(sum(r["avg_achievement"] for r in measured) / len(measured), 1) if measured else 0
    total_kpis = sum(r["total"] for r in rows)
    top = next((r for r in rows if r["measured"]), None)
    return {
        "year": year, "org_name": get_setting(db, "org_name", ""),
        "companies": rows,
        "total_companies": len(rows), "total_kpis": total_kpis,
        "holding_avg": holding_avg,
        "top_company": top["name"] if top else None,
        "counts": {k: sum(r["counts"][k] for r in rows) for k in (*STATUS_KEYS, "nodata")},
    }


@router.get("/companies")
def list_companies(db: Session = Depends(get_db), user=Depends(get_current_user)):
    out = []
    for c in db.query(models.OrgUnit).filter_by(level="company").order_by(models.OrgUnit.order).all():
        kpi_count = 0
        divs = db.query(models.OrgUnit).filter_by(level="division", parent_id=c.id).all()
        for d in divs:
            procs = db.query(models.OrgUnit).filter_by(level="process", parent_id=d.id).all()
            for p in procs:
                kpi_count += db.query(models.KPI).filter_by(process_id=p.id).count()
        out.append({"id": c.id, "code": c.code, "name": c.name,
                    "order": c.order, "kpi_count": kpi_count})
    return out


@router.post("/companies")
def create_company(body: dict, db: Session = Depends(get_db),
                   user=Depends(require_roles("admin"))):
    code = str(body.get("code", "")).strip().upper()
    name = str(body.get("name", "")).strip()
    if not code or not name:
        raise HTTPException(400, "کد و نام شرکت الزامی است")
    if db.query(models.OrgUnit).filter_by(level="company", code=code).first():
        raise HTTPException(400, "کد شرکت تکراری است")
    max_order = db.query(models.OrgUnit).filter_by(level="company").count()
    n = models.OrgUnit(code=code, name=name, level="company", order=max_order + 1)
    db.add(n); db.flush()
    log(db, user, "org", n.id, "create", field="company", new_value=name)
    db.commit()
    return {"id": n.id}


@router.put("/companies/{cid}")
def update_company(cid: int, body: dict, db: Session = Depends(get_db),
                   user=Depends(require_roles("admin"))):
    n = db.get(models.OrgUnit, cid)
    if not n or n.level != "company":
        raise HTTPException(404, "شرکت یافت نشد")
    name = str(body.get("name", n.name)).strip()
    if not name:
        raise HTTPException(400, "نام شرکت الزامی است")
    old = n.name
    n.name = name
    if body.get("code"):
        n.code = str(body["code"]).strip().upper()
    log(db, user, "org", n.id, "update", field="company",
        old_value=old, new_value=name)
    db.commit()
    return {"ok": True}


@router.delete("/companies/{cid}")
def delete_company(cid: int, db: Session = Depends(get_db),
                   user=Depends(require_roles("admin"))):
    n = db.get(models.OrgUnit, cid)
    if not n or n.level != "company":
        raise HTTPException(404, "شرکت یافت نشد")
    divs = db.query(models.OrgUnit).filter_by(level="division", parent_id=cid).all()
    for d in divs:
        procs = db.query(models.OrgUnit).filter_by(level="process", parent_id=d.id).all()
        for p in procs:
            if db.query(models.KPI).filter_by(process_id=p.id).count():
                raise HTTPException(400, "شرکت دارای شاخص است؛ ابتدا شاخص‌ها و فرایندها را منتقل یا حذف کنید")
    for d in divs:
        db.query(models.OrgUnit).filter_by(level="process", parent_id=d.id).delete()
        db.delete(d)
    log(db, user, "org", cid, "delete", field="company", old_value=n.name)
    db.delete(n)
    db.commit()
    return {"ok": True}
