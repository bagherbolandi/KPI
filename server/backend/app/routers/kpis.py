# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..schemas import KPIIn
from ..security import get_current_user, require_roles
from ..audit import log

router = APIRouter(prefix="/api/kpis", tags=["kpis"])

TRACKED = ["name", "target", "warning", "critical", "formula", "direction",
           "frequency", "weight", "importance", "calc_mode", "th_green", "th_yellow", "active"]


def kpi_dict(k: models.KPI, proc_name=None):
    return {
        "id": k.id, "code": k.code, "name": k.name, "process_id": k.process_id,
        "process_name": proc_name or (k.process.name if k.process else None),
        "uom": k.uom, "direction": k.direction, "frequency": k.frequency,
        "target": k.target, "warning": k.warning, "critical": k.critical,
        "weight": k.weight, "importance": k.importance, "is_strategic": k.is_strategic,
        "definition": k.definition, "formula": k.formula, "acceptance_text": k.acceptance_text,
        "calc_mode": k.calc_mode, "th_green": k.th_green, "th_yellow": k.th_yellow,
        "data_owner_id": k.data_owner_id, "approver_id": k.approver_id, "active": k.active,
        "is_mgt": bool(k.process and (k.process.code or "").strip().upper() == "MGT"),
    }


@router.get("")
def list_kpis(process_id: int | None = None, importance: str | None = None,
              strategic: bool | None = None, q: str | None = None,
              active: bool | None = None, company: int | None = None,
              db: Session = Depends(get_db), user=Depends(get_current_user)):
    query = db.query(models.KPI)
    # process owners see only their process
    if user.role.code == "process_owner" and user.process_id:
        query = query.filter(models.KPI.process_id == user.process_id)
    elif process_id:
        query = query.filter(models.KPI.process_id == process_id)
    if importance:
        query = query.filter(models.KPI.importance == importance)
    if strategic is not None:
        query = query.filter(models.KPI.is_strategic == strategic)
    if q:
        query = query.filter(models.KPI.name.contains(q) | models.KPI.code.contains(q))
    if active is not None:
        query = query.filter(models.KPI.active == active)
    kpis = query.order_by(models.KPI.code).all()
    if company:
        from ..effective import process_company_map, kpis_of_company
        kpis = kpis_of_company(kpis, company, process_company_map(db))
    procs = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    return [kpi_dict(k, procs.get(k.process_id)) for k in kpis]


@router.get("/{kid}")
def get_kpi(kid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    k = db.get(models.KPI, kid)
    if not k:
        raise HTTPException(404, "شاخص یافت نشد")
    return kpi_dict(k)


def _next_code(db, process_id):
    proc = db.get(models.OrgUnit, process_id)
    prefix = proc.code if proc else "GEN"
    n = db.query(models.KPI).filter(models.KPI.code.startswith(prefix + "-")).count()
    return f"{prefix}-{n+1:02d}"


@router.post("")
def create_kpi(body: KPIIn, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    code = body.code or _next_code(db, body.process_id)
    k = models.KPI(code=code, name=body.name, process_id=body.process_id, uom=body.uom,
                   direction=body.direction, frequency=body.frequency, target=body.target,
                   warning=body.warning, critical=body.critical, weight=body.weight,
                   importance=body.importance, is_strategic=body.is_strategic,
                   definition=body.definition, formula=body.formula,
                   acceptance_text=body.acceptance_text, calc_mode=body.calc_mode,
                   th_green=body.th_green, th_yellow=body.th_yellow,
                   data_owner_id=body.data_owner_id, approver_id=body.approver_id, active=body.active)
    db.add(k); db.flush()
    log(db, user, "kpi", k.code, "create", new_value=body.name, reason=body.reason)
    db.commit()
    return kpi_dict(k)


@router.put("/{kid}")
def update_kpi(kid: int, body: KPIIn, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    k = db.get(models.KPI, kid)
    if not k:
        raise HTTPException(404, "شاخص یافت نشد")
    if not body.reason:
        raise HTTPException(400, "برای ویرایش شاخص، ثبت «دلیل تغییر» الزامی است")
    # log every tracked field change
    for f in TRACKED:
        old = getattr(k, f)
        new = getattr(body, f)
        if str(old) != str(new):
            log(db, user, "kpi", k.code, "update", field=f, old_value=old, new_value=new, reason=body.reason)
            setattr(k, f, new)
    # non-tracked fields
    for f in ["definition", "acceptance_text", "uom", "data_owner_id", "approver_id",
              "is_strategic", "process_id"]:
        setattr(k, f, getattr(body, f))
    db.commit()
    return kpi_dict(k)


@router.delete("/{kid}")
def delete_kpi(kid: int, reason: str = Query("", description="دلیل حذف"),
               db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    k = db.get(models.KPI, kid)
    if not k:
        raise HTTPException(404, "شاخص یافت نشد")
    log(db, user, "kpi", k.code, "delete", old_value=k.name, reason=reason)
    db.query(models.KPIEntry).filter(models.KPIEntry.kpi_id == kid).delete()
    db.delete(k); db.commit()
    return {"ok": True}


# ============================== statistical analysis (offline parity) ==============================
from .. import stats as st  # noqa: E402
from ..calc import achievement  # noqa: E402
from ..effective import is_due, is_mgt  # noqa: E402
from ..jalali import month_name  # noqa: E402


def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


@router.get("/{kid}/analysis")
def kpi_analysis(kid: int,
                 fy: int = Query(None), fm: int = 1,
                 ty: int = Query(None), tm: int = 12,
                 alpha: float = 0.05, method: str = "paired",
                 approved_only: bool = False,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Range analysis: raw data, Welch or matched-month paired t, Holm family
    correction, slope trend test — ported from the offline analysis module."""
    k = db.get(models.KPI, kid)
    if not k:
        raise HTTPException(404, "شاخص یافت نشد")

    # default range: last 20 years of data ending at the newest entry/current year
    from ..settings_util import get_setting
    from ..jalali import today
    if fy is None or ty is None:
        years = [r[0] for r in db.query(models.KPIEntry.year)
                 .filter(models.KPIEntry.kpi_id == kid).distinct().all()]
        years.append(int(get_setting(db, "current_year", today()["year"])))
        end = max(years)
        fy, ty = max(end - 19, min(years)), end
    try:
        fy, fm, ty, tm = int(fy), int(fm), int(ty), int(tm)
    except (TypeError, ValueError):
        return {"error": "سال و ماه معتبر وارد کنید."}
    if not (1 <= fy and ty <= 9999 and 1 <= fm <= 12 and 1 <= tm <= 12):
        return {"error": "سال و ماه معتبر وارد کنید."}
    if fy * 12 + fm > ty * 12 + tm:
        return {"error": "ابتدای دامنه نباید پس از انتهای آن باشد."}
    if ty - fy >= 20:
        return {"error": "حداکثر دامنه قابل انتخاب ۲۰ سال است."}
    if alpha not in (0.01, 0.05, 0.1) or method not in ("welch", "paired"):
        return {"error": "روش آزمون یا سطح معناداری معتبر نیست."}

    # ---- points: due months inside range with a recorded value (entry-based)
    entries = (db.query(models.KPIEntry)
               .filter(models.KPIEntry.kpi_id == kid,
                       models.KPIEntry.year >= fy, models.KPIEntry.year <= ty,
                       models.KPIEntry.actual != None))  # noqa: E711
    if approved_only:
        entries = entries.filter(models.KPIEntry.workflow_state == "approved")
    emap = {(e.year, e.month): e for e in entries.all()}

    points = []
    for y in range(fy, ty + 1):
        for m in range(1, 13):
            if y * 12 + m < fy * 12 + fm or y * 12 + m > ty * 12 + tm:
                continue
            if not is_due(k.frequency, m):
                continue
            e = emap.get((y, m))
            v = _num(e.actual) if e else None
            if v is not None:
                points.append({"x": (y - fy) * 12 + m, "year": y, "month": m, "y": v})

    # ---- chart series (effective values; MGT derived)
    from ..effective import effective_actual
    labels, values = [], []
    for y in range(fy, ty + 1):
        for m in range(1, 13):
            if y * 12 + m < fy * 12 + fm or y * 12 + m > ty * 12 + tm:
                continue
            labels.append(f"{y}/{m:02d}")
            if is_mgt(k):
                values.append(effective_actual(db, k, y, m, approved_only=approved_only))
            else:
                e = emap.get((y, m))
                values.append(_num(e.actual) if e else None)

    # ---- per-year summary
    groups = {y: [p for p in points if p["year"] == y] for y in range(fy, ty + 1)}
    summary = []
    for y in range(fy, ty + 1):
        g = groups[y]
        n, mean, var = st.moments([p["y"] for p in g])
        mean_ach = achievement(mean, k.target, k.direction) if mean is not None else None
        summary.append({"year": y, "n": n, "mean": mean,
                        "std": (var ** 0.5) if var is not None else None,
                        "mean_ach": mean_ach,
                        "months": [month_name(p["month"]) for p in g]})

    # ---- year pairs with Holm correction
    rows = []
    for a in range(fy, ty + 1):
        for b in range(a + 1, ty + 1):
            r = st.compare_groups(
                [p["y"] for p in groups[a]], [p["y"] for p in groups[b]],
                method, alpha,
                [p["month"] for p in groups[a]], [p["month"] for p in groups[b]])
            r["yearA"], r["yearB"] = a, b
            rows.append(r)
    st.holm_adjust(rows, total=len(rows))
    for r in rows:
        r["decision"] = st.decision_text(r, k.direction, alpha)

    # ---- slope trend test (entry-based points, calendar spacing preserved)
    trend = st.slope_test([(p["x"], p["y"]) for p in points])
    trend["confidence"] = round((1 - alpha) * 100)
    if is_mgt(k):
        trend = {"n": 0, "df": None, "t": None, "p": None, "slope": None,
                 "state": "derived",
                 "title": "نیازمند بررسی مدیریتی",
                 "reason": ("مقادیر ماهانه این شاخص تجمعی و وابسته‌اند؛ آزمون T مستقل "
                            "روی آن‌ها معتبر نیست. روند شاخص‌های پایه بررسی شود.")}
    else:
        last_value = next((p["y"] for p in reversed(points)), None)
        trend = st.trend_review(trend, k.direction, k.target, last_value, alpha)

    return {
        "error": None,
        "range": {"fy": fy, "fm": fm, "ty": ty, "tm": tm,
                  "text": f"{fy}/{fm:02d} تا {ty}/{tm:02d}"},
        "alpha": alpha, "method": method,
        "method_label": "T زوجی ماه‌های مشترک" if method == "paired" else "T ولچ مستقل",
        "confidence": round((1 - alpha) * 100),
        "mgt": is_mgt(k),
        "mgt_warning": ("مقایسه T برای مقادیر تجمعی و وابسته مسئولیت مدیریت اجرا نمی‌شود؛ "
                        "شاخص‌های پایه را انتخاب کنید.") if is_mgt(k) else None,
        "approved_only": approved_only,
        "labels": labels, "values": values,
        "points": points, "summary": summary, "pairs": rows, "trend": trend,
        "uom": k.uom, "target": k.target, "direction": k.direction,
    }
