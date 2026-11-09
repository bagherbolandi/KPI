# -*- coding: utf-8 -*-
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from ..database import get_db
from .. import models
from ..security import get_current_user, require_roles
from ..settings_util import get_setting, set_setting, get_thresholds
from ..jalali import label, month_name, today, to_fa_digits
from ..audit import log
from .dashboard import _latest_entry_map

router = APIRouter(prefix="/api", tags=["reports"])

STATUS_FA = {"green": "سبز", "yellow": "زرد", "red": "قرمز", None: "بدون داده"}
STATUS_FILL = {"green": "C6EFCE", "yellow": "FFEB9C", "red": "FFC7CE", None: "F2F2F2"}


# ---------------- Excel export of KPI master + latest values ----------------
@router.get("/export/excel")
def export_excel(year: int = Query(None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    year = year or int(get_setting(db, "current_year", today()["year"]))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "KPIs"
    ws.sheet_view.rightToLeft = True
    headers = ["کد", "شاخص", "فرایند", "واحد", "جهت", "تناوب", "هدف", "حد هشدار",
               "حد بحرانی", "وزن", "اهمیت", "عملکرد واقعی", "درصد تحقق", "وضعیت", "دوره"]
    hfill = PatternFill("solid", fgColor="1F4E78")
    hfont = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h); cell.fill = hfill; cell.font = hfont
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    latest = _latest_entry_map(db, year)
    procs = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    r = 2
    for k in db.query(models.KPI).order_by(models.KPI.code).all():
        e = latest.get(k.id)
        ach = round(e.achievement * 100, 1) if e and e.achievement is not None else None
        st = e.status if e else None
        row = [k.code, k.name, procs.get(k.process_id), k.uom,
               "صعودی" if k.direction == "up" else "نزولی", k.frequency,
               k.target, k.warning, k.critical, k.weight,
               "کلیدی" if k.importance == "key" else "عملیاتی",
               e.actual if e else None, ach, STATUS_FA.get(st),
               label(e.year, e.month) if e else "—"]
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v); cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(r, 14).fill = PatternFill("solid", fgColor=STATUS_FILL.get(st))
        r += 1
    widths = [10, 42, 22, 10, 8, 10, 9, 9, 9, 7, 9, 12, 11, 10, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    fname = f"KPI_Report_{year}.xlsx"
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"})


# ---------------- PDF management report ----------------
@router.get("/export/pdf")
def export_pdf(year: int = Query(None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # register the bundled Persian font (Vazirmatn)
    fontdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
    fontname = "Helvetica"
    reg = os.path.join(fontdir, "Vazirmatn-Regular.ttf")
    bold = os.path.join(fontdir, "Vazirmatn-Bold.ttf")
    if os.path.exists(reg):
        pdfmetrics.registerFont(TTFont("Vazir", reg)); fontname = "Vazir"
        if os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("Vazir-Bold", bold))
    elif os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        fontname = "DejaVu"

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        def fa(t):
            return get_display(arabic_reshaper.reshape(str(t)))
    except Exception:
        def fa(t):
            return str(t)

    year = year or int(get_setting(db, "current_year", today()["year"]))
    from .dashboard import overview, by_process, critical
    ov = overview(year=year, db=db, user=user)
    procs = by_process(year=year, db=db, user=user)
    crit = critical(year=year, db=db, user=user)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Title"], fontName=fontname, alignment=1, fontSize=16)
    n = ParagraphStyle("n", parent=styles["Normal"], fontName=fontname, alignment=2, fontSize=10)
    story = [Paragraph(fa(f"گزارش مدیریتی پایش شاخص‌های عملکرد — سال {to_fa_digits(year)}"), h),
             Paragraph(fa(ov["org_name"]), n), Spacer(1, 8*mm)]

    summary = [[fa("کل شاخص‌ها"), fa("سبز"), fa("زرد"), fa("قرمز"), fa("بدون داده"), fa("میانگین تحقق")],
               [to_fa_digits(ov["total"]), to_fa_digits(ov["counts"]["green"]),
                to_fa_digits(ov["counts"]["yellow"]), to_fa_digits(ov["counts"]["red"]),
                to_fa_digits(ov["counts"]["nodata"]), to_fa_digits(f"{ov['avg_achievement']}%")]]
    t = Table(summary, colWidths=[30*mm]*6)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), fontname), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story += [t, Spacer(1, 8*mm), Paragraph(fa("رتبه‌بندی عملکرد فرایندها"), n), Spacer(1, 3*mm)]

    prows = [[fa("فرایند"), fa("تعداد"), fa("سبز"), fa("زرد"), fa("قرمز"), fa("میانگین تحقق")]]
    for p in procs:
        prows.append([fa(p["name"]), to_fa_digits(p["total"]), to_fa_digits(p["counts"]["green"]),
                      to_fa_digits(p["counts"]["yellow"]), to_fa_digits(p["counts"]["red"]),
                      to_fa_digits(f"{p['avg_achievement']}%")])
    pt = Table(prows, colWidths=[55*mm, 20*mm, 18*mm, 18*mm, 18*mm, 28*mm])
    pt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), fontname), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FB")])]))
    story += [pt, Spacer(1, 8*mm),
              Paragraph(fa(f"شاخص‌های بحرانی ({to_fa_digits(len(crit))} مورد)"), n), Spacer(1, 3*mm)]

    crows = [[fa("کد"), fa("شاخص"), fa("فرایند"), fa("هدف"), fa("واقعی"), fa("تحقق")]]
    for c in crit[:25]:
        crows.append([fa(c["code"]), fa(c["name"][:38]), fa(c["process"]),
                      to_fa_digits(c["target"]), to_fa_digits(c["actual"]),
                      to_fa_digits(f"{c['achievement']}%") if c["achievement"] is not None else "—"])
    ct = Table(crows, colWidths=[18*mm, 62*mm, 38*mm, 16*mm, 16*mm, 16*mm])
    ct.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), fontname), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C00000")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(ct)
    doc.build(story)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=Mgmt_Report_{year}.pdf"})


# ---------------- Audit log ----------------
@router.get("/audit")
def audit(limit: int = 200, entity_type: str = None, db: Session = Depends(get_db),
          user=Depends(require_roles("admin", "quality"))):
    q = db.query(models.AuditLog)
    if entity_type:
        q = q.filter(models.AuditLog.entity_type == entity_type)
    rows = q.order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "username": r.username, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "action": r.action, "field": r.field,
             "old_value": r.old_value, "new_value": r.new_value, "reason": r.reason,
             "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")} for r in rows]


# ---------------- Settings ----------------
@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    g, y = get_thresholds(db)
    return {"th_green": g, "th_yellow": y,
            "org_name": get_setting(db, "org_name", ""),
            "current_year": get_setting(db, "current_year", str(today()["year"])),
            "recovery_enabled": get_setting(db, "recovery_enabled", "1"),
            "session_hours": get_setting(db, "session_hours", "12")}


@router.put("/settings")
def update_settings(body: dict, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    for k in ["th_green", "th_yellow", "org_name", "current_year",
              "recovery_enabled"]:
        if k in body and body[k] is not None:
            old = get_setting(db, k, "")
            set_setting(db, k, str(body[k]))
            log(db, user, "setting", k, "update", field=k, old_value=old, new_value=body[k])
    db.commit()
    return {"ok": True}


@router.get("/meta")
def meta(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Reference lists for the UI (years, months, enums)."""
    years = [r[0] for r in db.query(models.KPIEntry.year).distinct().order_by(models.KPIEntry.year.desc()).all()]
    return {
        "years": years,
        "months": [{"num": i, "name": month_name(i)} for i in range(1, 13)],
        "current_year": int(get_setting(db, "current_year", today()["year"])),
        "current_month": today()["month"],
        "today": today(),
        "frequencies": {"monthly": "ماهانه", "quarterly": "سه‌ماهه",
                        "semiannual": "شش‌ماهه", "annual": "سالانه", "event": "رویدادی"},
        "uoms": {"percent": "درصد", "count": "تعداد", "count_per_month": "تعداد در ماه",
                 "times_per_year": "بار در سال", "days": "روز", "hours": "ساعت",
                 "ppm": "PPM", "person": "نفر", "number": "عدد", "currency": "ریال"},
        "importance": {"strategic": "راهبردی", "core": "کلیدی",
                       "operational": "عملیاتی"},
        "views": [{"key": k, "label": VIEW_LABELS[k]} for k in VIEW_KEYS],
        "companies": [{"id": c.id, "code": c.code, "name": c.name,
                       "order": c.order}
                      for c in db.query(models.OrgUnit).filter_by(level="company")
                      .order_by(models.OrgUnit.order).all()],
        "calc_mode": get_setting(db, "calc_mode", "achievement"),
        "thresholds": get_thresholds(db),
        "org_name": get_setting(db, "org_name", ""),
        "app_version": "1.1.0",
    }


# ==================================================================== #
#  Offline-parity reports: range report, no-data report, list exports, #
#  CSV, backup/restore, sample data management                         #
# ==================================================================== #
import csv as csv_mod
import json
from datetime import datetime

from ..effective import is_due, is_mgt, mgt_actual, process_company_map, kpis_of_company
from ..permissions import VIEW_KEYS, VIEW_LABELS
from ..calc import achievement, status_from_achievement, evaluate
from ..settings_util import get_setting as _gs

FA_DIGITS_MAP = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
                 "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
                 "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
                 "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"}


def _en(s) -> str:
    s = str(s)
    return "".join(FA_DIGITS_MAP.get(c, c) for c in s)


def parse_jalali_date(s):
    """Offline parseJalaliDate: '1405/01/01' -> num or None."""
    if not s:
        return None
    t = _en(s).strip().replace("-", "/").replace(" ", "")
    parts = t.split("/")
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if not y or not m or not d or m < 1 or m > 12 or d < 1 or d > 31:
        return None
    return y * 10000 + m * 100 + d


def parse_range(from_s, to_s):
    f = parse_jalali_date(from_s)
    t = parse_jalali_date(to_s)
    if f is None or t is None:
        return None
    a, b = f, t
    if a > b:
        a, b = b, a
    return a, b


def months_in_range(from_num: int, to_num: int):
    fy, fm = from_num // 10000, (from_num % 10000) // 100
    ty, tm = to_num // 10000, (to_num % 10000) // 100
    out = []
    y, m = fy, fm
    while (y < ty or (y == ty and m <= tm)) and len(out) <= 600:
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def status_band2(actual, target, warning, direction, th_g, th_y):
    """Offline statusByTargetWarning: numeric target/warning band, falling back
    to achievement thresholds when warning is absent or equals target."""
    if actual is None:
        return None
    if warning is None or warning == target:
        return status_from_achievement(achievement(actual, target, direction), th_g, th_y)
    a, t, w = float(actual), float(target), float(warning)
    if direction == "down":
        if a <= t:
            return "green"
        if a <= w:
            return "yellow"
        return "red"
    if a >= t:
        return "green"
    if a >= w:
        return "yellow"
    return "red"


def _range_filters(db, process_id, importance, company, proc_company):
    kpis = db.query(models.KPI).filter(models.KPI.active == True).all()  # noqa
    if company:
        kpis = kpis_of_company(kpis, company, proc_company)
    if process_id:
        kpis = [k for k in kpis if k.process_id == process_id]
    if importance == "strategic":
        kpis = [k for k in kpis if k.is_strategic]
    elif importance == "key":
        kpis = [k for k in kpis if k.importance == "key"]
    elif importance == "operational":
        kpis = [k for k in kpis if k.importance == "operational"]
    return kpis


def range_core(db, from_s, to_s, basis="avg", process_id=None, status_f=None,
               importance=None, approved_only=False, company=None):
    rng = parse_range(from_s, to_s)
    if rng is None:
        raise HTTPException(400, "فرمت تاریخ نادرست است. مثال صحیح: 1404/05/01")
    from_num, to_num = rng
    th_g, th_y = get_thresholds(db)
    proc_company = process_company_map(db)
    kpis = _range_filters(db, process_id, importance, company, proc_company)

    # entries inside the range with numeric actual
    q = db.query(models.KPIEntry).filter(
        models.KPIEntry.actual != None,  # noqa: E711
        models.KPIEntry.year * 10000 + models.KPIEntry.month * 100 + 1 >= from_num,
        models.KPIEntry.year * 10000 + models.KPIEntry.month * 100 + 1 <= to_num)
    if approved_only:
        q = q.filter(models.KPIEntry.workflow_state == "approved")
    by_kpi = {}
    for e in q.all():
        by_kpi.setdefault(e.kpi_id, []).append(e)

    rows = []
    for k in kpis:
        pts = []
        if is_mgt(k):
            for (y, m) in months_in_range(from_num, to_num):
                act = mgt_actual(db, y, m, approved_only=approved_only,
                                 proc_company=proc_company, company_id=company)
                if act is not None:
                    pts.append((y * 10000 + m * 100 + 1, act))
        else:
            for e in by_kpi.get(k.id, []):
                pts.append((e.year * 10000 + e.month * 100 + 1, float(e.actual)))
        if not pts:
            continue
        pts.sort(key=lambda p: p[0])
        vals = [p[1] for p in pts]
        avg_act = sum(vals) / len(vals)
        last = vals[-1]
        achs = [a for a in (achievement(v, k.target, k.direction) for v in vals) if a is not None]
        basis_val = last if basis == "last" else avg_act
        avg_ach = (achievement(last, k.target, k.direction) if basis == "last"
                   else (sum(achs) / len(achs) if achs else None))
        rows.append({
            "kpi_id": k.id, "code": k.code, "name": k.name,
            "process_id": k.process_id,
            "process": k.process.name if k.process else "",
            "uom": k.uom, "frequency": k.frequency, "direction": k.direction,
            "target": k.target, "warning": k.warning, "weight": k.weight or 1,
            "is_strategic": k.is_strategic, "importance": k.importance,
            "count": len(vals), "avg_actual": round(avg_act, 2), "last": last,
            "avg_ach": (round(avg_ach, 4) if avg_ach is not None else None),
            "status": status_band2(basis_val, k.target, k.warning,
                                   k.direction, th_g, th_y),
            "mgt": is_mgt(k),
        })
    rows.sort(key=lambda r: (r["avg_ach"] is None, r["avg_ach"] or 0))

    rows_f = [r for r in rows if not status_f or r["status"] == status_f]
    total = len(rows_f)
    f_sum = sum(r["avg_ach"] for r in rows_f if r["avg_ach"] is not None)
    n_ach = sum(1 for r in rows_f if r["avg_ach"] is not None)
    w_den = sum(r["weight"] for r in rows_f if r["avg_ach"] is not None)
    w_num = sum(r["avg_ach"] * r["weight"] for r in rows_f if r["avg_ach"] is not None)
    counts = {"green": 0, "yellow": 0, "red": 0, "nodata": 0}
    for r in rows_f:
        counts[r["status"] or "nodata"] += 1
    agg = {
        "total": total,
        "avg": (f_sum / n_ach) if n_ach else 0,
        "weighted": (w_num / w_den) if w_den else 0,
        "counts": counts,
        "all_with_data": len(rows),
    }
    nd = None
    if not status_f:
        nd = nodata_core(db, from_s, to_s, process_id, importance,
                         None, approved_only, company)
    return {"from": _en(f"{from_num // 10000}/{(from_num % 10000) // 100:02d}/{from_num % 100:02d}"),
            "to": _en(f"{to_num // 10000}/{(to_num % 10000) // 100:02d}/{to_num % 100:02d}"),
            "basis": basis, "approved_only": approved_only,
            "rows": rows_f, "agg": agg, "nodata": nd,
            "from_num": from_num, "to_num": to_num}


def period_span(k):
    f = k.frequency or "monthly"
    return {"quarterly": 3, "semiannual": 6, "annual": 12}.get(f, 1)


def period_label(k, y, m, multi):
    f = k.frequency or "monthly"
    if f == "quarterly":
        t = ["بهار", "تابستان", "پاییز", "زمستان"][m // 3 - 1]
    elif f == "semiannual":
        t = "نیمه اول" if m == 6 else "نیمه دوم"
    elif f == "annual":
        t = "سالانه"
    else:
        t = month_name(m)
    return t + (f" {y}" if (multi or f == "annual") else "")


def nodata_core(db, from_s, to_s, process_id=None, importance=None, kind=None,
                approved_only=False, company=None):
    """Offline noDataAnalysis: due periods without a numeric value."""
    rng = parse_range(from_s, to_s)
    if rng is None:
        raise HTTPException(400, "فرمت تاریخ نادرست است. مثال صحیح: 1405/01/01")
    from_num, to_num = rng
    months = months_in_range(from_num, to_num)
    multi = bool(months) and months[0][0] != months[-1][0]
    proc_company = process_company_map(db)
    kpis = _range_filters(db, process_id, importance, company, proc_company)

    q = db.query(models.KPIEntry).filter(
        models.KPIEntry.actual != None,  # noqa: E711
        models.KPIEntry.year * 10000 + models.KPIEntry.month * 100 + 1 >= from_num,
        models.KPIEntry.year * 10000 + models.KPIEntry.month * 100 + 1 <= to_num)
    if approved_only:
        q = q.filter(models.KPIEntry.workflow_state == "approved")
    has = {}
    for e in q.all():
        has.setdefault(e.kpi_id, set()).add(f"{e.year}-{e.month}")

    rows = []
    considered = 0
    for k in kpis:
        if is_mgt(k):
            continue
        got = has.get(k.id, set())
        f = k.frequency or "monthly"
        if f in ("event", "per_ecn"):
            considered += 1
            if not got:
                rows.append({"kpi_id": k.id, "code": k.code, "name": k.name,
                             "process": k.process.name if k.process else "",
                             "frequency": f, "kind": "none",
                             "expected": None, "got": 0, "missing": []})
            continue
        due = [(y, m) for (y, m) in months if is_due(f, m)]
        if not due:
            continue
        considered += 1
        span = period_span(k)
        missing = []
        for (y, m) in due:
            ok = False
            for i in range(span):
                if f"{y}-{m - i}" in got:
                    ok = True
                    break
            if not ok:
                missing.append(period_label(k, y, m, multi))
        if missing:
            rows.append({"kpi_id": k.id, "code": k.code, "name": k.name,
                         "process": k.process.name if k.process else "",
                         "frequency": f,
                         "kind": "none" if len(missing) == len(due) else "partial",
                         "expected": len(due), "got": len(due) - len(missing),
                         "missing": missing})
    if kind in ("none", "partial"):
        rows = [r for r in rows if r["kind"] == kind]
    rows.sort(key=lambda r: (0 if r["kind"] == "none" else 1, r["process"], r["code"]))
    none_c = sum(1 for r in rows if r["kind"] == "none")
    return {"from": _en(f"{from_num // 10000}/{(from_num % 10000) // 100:02d}/{from_num % 100:02d}"),
            "to": _en(f"{to_num // 10000}/{(to_num % 10000) // 100:02d}/{to_num % 100:02d}"),
            "rows": rows, "none": none_c, "partial": len(rows) - none_c,
            "considered": considered, "approved_only": approved_only}


def _csv_response(rows, filename):
    import io
    buf = io.StringIO()
    w = csv_mod.writer(buf)
    for r in rows:
        w.writerow(r)
    data = "﻿" + buf.getvalue()  # BOM for Excel
    from fastapi.responses import Response
    return Response(content=data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


def _xlsx_response(wb, filename):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


def _sheet(ws, headers, rows, status_col=None):
    ws.sheet_view.rightToLeft = True
    hfill = PatternFill("solid", fgColor="1F4E78")
    hfont = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.fill = hfill; cell.font = hfont
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    for r, row in enumerate(rows, 2):
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        if status_col is not None:
            st = rows[r - 2][status_col]
            key = {"سبز": "green", "زرد": "yellow", "قرمز": "red"}.get(st)
            if key:
                ws.cell(r, status_col + 1).fill = PatternFill(
                    "solid", fgColor=STATUS_FILL.get(key))
    ws.freeze_panes = "A2"


IMP_FA = {"strategic": "استراتژیک", "key": "کلیدی", "operational": "عادی (عملیاتی)", None: "همه"}


# ----------------------------- range report endpoints
@router.get("/reports/range")
def report_range(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                 basis: str = "avg", process_id: int | None = None,
                 status: str | None = None, importance: str | None = None,
                 approved_only: bool = False, company: int | None = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    if basis not in ("avg", "last"):
        raise HTTPException(400, "مبنای ارزیابی نامعتبر است")
    return range_core(db, from_date, to_date, basis, process_id, status,
                      importance, approved_only, company)


@router.get("/reports/range.csv")
def report_range_csv(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                     basis: str = "avg", process_id: int | None = None,
                     status: str | None = None, importance: str | None = None,
                     approved_only: bool = False, company: int | None = None,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = range_core(db, from_date, to_date, basis, process_id, status,
                   importance, approved_only, company)
    out = [["کد", "نام شاخص", "فرایند", "تعداد ثبت", "میانگین عملکرد",
            "آخرین مقدار", "تحقق (طبق مبنا)", "وضعیت بازه"]]
    STATUS_FA = {"green": "سبز", "yellow": "زرد", "red": "قرمز"}
    for x in r["rows"]:
        out.append([x["code"], x["name"], x["process"], x["count"],
                    x["avg_actual"], x["last"],
                    "" if x["avg_ach"] is None else round(x["avg_ach"] * 100, 1),
                    STATUS_FA.get(x["status"], "")])
    return _csv_response(out, "KPI_Range_Report.csv")


@router.get("/reports/range.xlsx")
def report_range_xlsx(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                      basis: str = "avg", process_id: int | None = None,
                      status: str | None = None, importance: str | None = None,
                      approved_only: bool = False, company: int | None = None,
                      db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = range_core(db, from_date, to_date, basis, process_id, status,
                   importance, approved_only, company)
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Range"
    STATUS_FA = {"green": "سبز", "yellow": "زرد", "red": "قرمز"}
    data = [[x["code"], x["name"], x["process"], x["count"], x["avg_actual"],
             x["last"],
             None if x["avg_ach"] is None else round(x["avg_ach"] * 100, 1),
             STATUS_FA.get(x["status"], "بدون داده")] for x in r["rows"]]
    _sheet(ws, ["کد", "نام شاخص", "فرایند", "تعداد ثبت", "میانگین عملکرد",
                "آخرین مقدار", "تحقق (٪)", "وضعیت بازه"], data, status_col=7)
    return _xlsx_response(wb, "KPI_Range_Report.xlsx")


@router.get("/reports/range.pdf")
def report_range_pdf(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                     basis: str = "avg", process_id: int | None = None,
                     status: str | None = None, importance: str | None = None,
                     approved_only: bool = False, company: int | None = None,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = range_core(db, from_date, to_date, basis, process_id, status,
                   importance, approved_only, company)
    return _pdf_table(
        title=f"گزارش بازه‌ای شاخص‌ها — {r['from']} تا {r['to']}",
        subtitle=(f"مبنای ارزیابی: {'آخرین مقدار' if basis == 'last' else 'میانگین دوره'} · "
                  f"داده: {'فقط تأییدشده' if approved_only else 'همه داده‌های ثبت‌شده'}"),
        headers=["کد", "نام شاخص", "فرایند", "ثبت", "میانگین", "آخرین", "تحقق", "وضعیت"],
        rows=[[x["code"], x["name"][:34], x["process"][:20], x["count"],
               x["avg_actual"], x["last"],
               "—" if x["avg_ach"] is None else f"{round(x['avg_ach'] * 100)}%",
               {"green": "سبز", "yellow": "زرد", "red": "قرمز"}.get(x["status"], "—")]
              for x in r["rows"]],
        filename="KPI_Range_Report.pdf")


# ----------------------------- no-data report endpoints
@router.get("/reports/no-data")
def report_nodata(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                  process_id: int | None = None, importance: str | None = None,
                  kind: str | None = None, approved_only: bool = False,
                  company: int | None = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    if kind not in (None, "", "none", "partial"):
        raise HTTPException(400, "نوع گزارش نامعتبر است")
    return nodata_core(db, from_date, to_date, process_id, importance,
                       kind or None, approved_only, company)


@router.get("/reports/no-data.xlsx")
def report_nodata_xlsx(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                       process_id: int | None = None, importance: str | None = None,
                       kind: str | None = None, approved_only: bool = False,
                       company: int | None = None,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = nodata_core(db, from_date, to_date, process_id, importance,
                    kind or None, approved_only, company)
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "NoData"
    data = [[x["code"], x["name"], x["process"],
             {"monthly": "ماهانه", "quarterly": "فصلی", "semiannual": "شش‌ماهه",
              "annual": "سالانه", "event": "رویدادی"}.get(x["frequency"], x["frequency"]),
             "بدون داده" if x["kind"] == "none" else f"ناقص ({x['got']} از {x['expected']})",
             "هیچ مقداری ثبت نشده" if x["expected"] is None else "، ".join(x["missing"])]
            for x in r["rows"]]
    _sheet(ws, ["کد", "نام شاخص", "فرایند", "تناوب پایش", "وضعیت ثبت",
                "دوره‌های بدون ثبت"], data)
    return _xlsx_response(wb, "KPI_NoData_Report.xlsx")


@router.get("/reports/no-data.pdf")
def report_nodata_pdf(from_date: str = Query(alias="from"), to_date: str = Query(alias="to"),
                      process_id: int | None = None, importance: str | None = None,
                      kind: str | None = None, approved_only: bool = False,
                      company: int | None = None,
                      db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = nodata_core(db, from_date, to_date, process_id, importance,
                    kind or None, approved_only, company)
    return _pdf_table(
        title=f"گزارش شاخص‌های فاقد داده — {r['from']} تا {r['to']}",
        subtitle=(f"دارای سررسید: {r['considered']} · بدون داده: {r['none']} · "
                  f"ناقص: {r['partial']}"),
        headers=["کد", "نام شاخص", "فرایند", "تناوب", "وضعیت ثبت", "دوره‌های بدون ثبت"],
        rows=[[x["code"], x["name"][:34], x["process"][:20],
               {"monthly": "ماهانه", "quarterly": "فصلی", "semiannual": "شش‌ماهه",
                "annual": "سالانه", "event": "رویدادی"}.get(x["frequency"], x["frequency"]),
               "بدون داده" if x["kind"] == "none" else f"ناقص ({x['got']}/{x['expected']})",
               ("هیچ مقداری ثبت نشده" if x["expected"] is None
                else "، ".join(x["missing"][:6]) + ("…" if len(x["missing"]) > 6 else ""))]
              for x in r["rows"]],
        filename="KPI_NoData_Report.pdf")


# ----------------------------- shared PDF builder
def _pdf_table(title, subtitle, headers, rows, filename):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os as _os
    fontdir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "fonts")
    fontname = "Helvetica"
    reg = _os.path.join(fontdir, "Vazirmatn-Regular.ttf")
    if _os.path.exists(reg):
        pdfmetrics.registerFont(TTFont("Vazir", reg))
        fontname = "Vazir"
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        def fa(t):
            return get_display(arabic_reshaper.reshape(str(t)))
    except Exception:
        def fa(t):
            return str(t)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Title"], fontName=fontname, alignment=1, fontSize=14)
    n = ParagraphStyle("n", parent=styles["Normal"], fontName=fontname, alignment=2, fontSize=9)
    story = [Paragraph(fa(title), h), Paragraph(fa(subtitle), n), Spacer(1, 5 * mm)]
    t = Table([[fa(str(c)) for c in headers]] + [[fa(str(c)) for c in r] for r in rows],
              colWidths=[16 * mm, 52 * mm, 30 * mm, 16 * mm, 24 * mm, 46 * mm][:len(headers)])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), fontname), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FB")]),
    ]))
    story.append(t)
    doc.build(story)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


# ----------------------------- KPI list exports (active/inactive/all)
def _list_rows(db, scope):
    q = db.query(models.KPI)
    if scope == "active":
        q = q.filter(models.KPI.active == True)  # noqa
    elif scope == "inactive":
        q = q.filter(models.KPI.active == False)  # noqa
    procs = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    out = []
    for k in q.order_by(models.KPI.code).all():
        out.append([k.code, k.name, procs.get(k.process_id, ""),
                    k.uom, "صعودی" if k.direction == "up" else "نزولی",
                    k.frequency, k.target, k.warning, k.critical, k.weight,
                    "استراتژیک" if k.is_strategic else
                    ("کلیدی" if k.importance == "key" else "عملیاتی"),
                    k.acceptance_text, "فعال" if k.active else "غیرفعال"])
    return out


LIST_HEADERS = ["کد", "نام شاخص", "فرایند", "واحد", "جهت", "تناوب", "هدف",
                "حد هشدار", "حد بحرانی", "وزن", "اهمیت", "معیار پذیرش", "وضعیت"]


@router.get("/reports/list")
def report_list(scope: str = "all", format: str = "json",
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    if scope not in ("all", "active", "inactive"):
        raise HTTPException(400, "دامنه نامعتبر است")
    rows = _list_rows(db, scope)
    if format == "csv":
        return _csv_response([LIST_HEADERS] + rows, f"KPI_List_{scope}.csv")
    if format == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active; ws.title = "KPI List"
        _sheet(ws, LIST_HEADERS, rows)
        return _xlsx_response(wb, f"KPI_List_{scope}.xlsx")
    return {"headers": LIST_HEADERS, "rows": rows, "scope": scope,
            "count": len(rows)}


# ----------------------------- comprehensive CSV
@router.get("/export/csv")
def export_csv(year: int = Query(None), db: Session = Depends(get_db),
               user=Depends(get_current_user)):
    from .dashboard import _latest_entry_map
    year = year or int(get_setting(db, "current_year", today()["year"]))
    latest = _latest_entry_map(db, year)
    procs = {p.id: p.name for p in db.query(models.OrgUnit).all()}
    out = [["کد", "شاخص", "فرایند", "واحد", "جهت", "تناوب", "هدف", "حد هشدار",
            "حد بحرانی", "وزن", "اهمیت", "عملکرد واقعی", "درصد تحقق", "وضعیت", "دوره"]]
    STATUS_FA = {"green": "سبز", "yellow": "زرد", "red": "قرمز"}
    for k in db.query(models.KPI).order_by(models.KPI.code).all():
        e = latest.get(k.id)
        out.append([k.code, k.name, procs.get(k.process_id), k.uom,
                    "صعودی" if k.direction == "up" else "نزولی", k.frequency,
                    k.target, k.warning, k.critical, k.weight,
                    "کلیدی" if k.importance == "key" else "عملیاتی",
                    e.actual if e else None,
                    round(e.achievement * 100, 1) if e and e.achievement is not None else None,
                    STATUS_FA.get(e.status, "") if e else "",
                    label(e.year, e.month) if e else "—"])
    return _csv_response(out, f"KPI_Report_{year}.csv")


# ----------------------------- backup / restore (offline backup/restore)
BACKUP_TABLES = [
    ("settings", models.Setting, ["key", "value"]),
    ("roles", models.Role, ["id", "code", "name_fa", "name_en", "description"]),
    ("users", models.User, ["id", "username", "full_name", "email", "hashed_password",
                            "role_id", "process_id", "is_active", "permissions",
                            "must_change"]),
    ("org_units", models.OrgUnit, ["id", "code", "name", "level", "parent_id",
                                   "owner_user_id", "order"]),
    ("kpis", models.KPI, ["id", "code", "name", "process_id", "uom", "direction",
                          "frequency", "target", "warning", "critical", "weight",
                          "importance", "is_strategic", "definition", "formula",
                          "acceptance_text", "calc_mode", "th_green", "th_yellow",
                          "data_owner_id", "approver_id", "active"]),
    ("kpi_entries", models.KPIEntry, ["id", "kpi_id", "year", "month", "actual",
                                      "achievement", "status", "comment",
                                      "deviation_cause", "corrective_action",
                                      "workflow_state", "submitted_by",
                                      "submitted_at", "reviewed_by", "reviewed_at",
                                      "approved_by", "approved_at",
                                      "rejection_reason"]),
    ("strategy_goals", models.StrategyGoal, ["id", "company_id", "title", "description",
                                             "owner_process_code", "start_period",
                                             "end_period", "archived", "sample_key"]),
    ("strategy_links", models.StrategyLink, ["id", "goal_id", "kpi_id", "mode",
                                             "baseline", "snapshot"]),
    ("strategy_actions", models.StrategyAction, ["id", "goal_id", "link_id", "title",
                                                 "description", "owner_user_id",
                                                 "due_period", "rule", "threshold",
                                                 "state", "progress", "evidence"]),
    ("strategy_events", models.StrategyEvent, ["id", "goal_id", "at", "by_user_id",
                                               "type", "details"]),
    ("audit_logs", models.AuditLog, ["id", "user_id", "username", "entity_type",
                                     "entity_id", "action", "field", "old_value",
                                     "new_value", "reason", "created_at"]),
]


def _ser(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _de(v, typ=None):
    if isinstance(v, str) and typ in (datetime,):
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return v


@router.get("/reports/backup")
def report_backup(db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    data = {}
    for name, model, cols in BACKUP_TABLES:
        items = []
        for row in db.query(model).all():
            items.append({c: _ser(getattr(row, c)) for c in cols})
        data[name] = items
    payload = {"format": "kpi-ms-backup", "version": 1,
               "exported_at": datetime.utcnow().isoformat(),
               "exported_by": user.username, "data": data}
    from fastapi.responses import Response
    return Response(content=json.dumps(payload, ensure_ascii=False, default=str),
                    media_type="application/json",
                    headers={"Content-Disposition":
                             f"attachment; filename=kpi-backup-{datetime.utcnow().strftime('%Y%m%d')}.json"})


@router.post("/reports/restore")
def report_restore(body: dict, db: Session = Depends(get_db),
                   user=Depends(require_roles("admin"))):
    payload = body.get("data") if isinstance(body.get("data"), dict) else body
    if payload.get("format") not in (None, "kpi-ms-backup") and "data" not in body:
        raise HTTPException(400, "فایل پشتیبان نامعتبر است")
    data = payload.get("data", payload)
    if not data.get("kpis"):
        raise HTTPException(400, "فایل پشتیبان شاخصی ندارد؛ بازیابی انجام نشد")
    # wipe in FK-safe order (children first); settings are upserted below
    for name, model, cols in reversed(BACKUP_TABLES):
        if name == "settings":
            continue
        db.query(model).delete()
    db.flush()
    dt_cols = {"created_at", "submitted_at", "reviewed_at", "approved_at", "at",
               "updated_at"}
    for name, model, cols in BACKUP_TABLES:
        for item in data.get(name, []):
            kw = {}
            for c in cols:
                if c in item:
                    kw[c] = _de(item[c], datetime if c in dt_cols else None)
            try:
                if name == "settings":
                    set_setting(db, kw.get("key"), kw.get("value", ""))
                    continue
                db.add(model(**kw))
            except Exception as ex:
                raise HTTPException(400, f"بازیابی جدول {name} ناموفق بود: {ex}")
        db.flush()
    log(db, user, "system", "-", "restore",
        new_value="بازیابی از پشتیبان", reason="restore")
    db.commit()
    return {"ok": True, "tables": [n for n, _, _ in BACKUP_TABLES]}


# ----------------------------- settings: sample data / clear (offline parity)
@router.post("/settings/load-sample")
def settings_load_sample(db: Session = Depends(get_db),
                         user=Depends(require_roles("admin"))):
    """Offline loadSample: regenerate performance entries for the current year."""
    import random
    _t = today()
    year = int(get_setting(db, "current_year", _t["year"]))
    # never fabricate future periods: stop at the current Jalali month for the
    # current year (whole year for past years)
    last_month = _t["month"] if year == _t["year"] else 12
    db.query(models.KPIEntry).filter(models.KPIEntry.year == year).delete()
    th_g, th_y = get_thresholds(db)
    created = 0
    for k in db.query(models.KPI).filter(models.KPI.active == True).all():  # noqa
        if is_mgt(k):
            continue
        for m in range(1, last_month + 1):
            if not is_due(k.frequency, m):
                continue
            r = random.random()
            if k.direction == "up":
                factor = (0.9 + random.random() * 0.12) if r < 0.6 else \
                         (0.6 + random.random() * 0.25) if r < 0.85 else \
                         (0.3 + random.random() * 0.25)
            else:
                factor = (0.9 + random.random() * 0.12) if r < 0.6 else \
                         (1.1 + random.random() * 0.4) if r < 0.85 else \
                         (1.4 + random.random() * 0.5)
            actual = round(k.target * factor, 2)
            ach, st = evaluate(k, actual, th_g, th_y)
            ws = "qc_reviewed" if m == 12 else "approved"
            db.add(models.KPIEntry(kpi_id=k.id, year=year, month=m, actual=actual,
                                   achievement=ach, status=st, workflow_state=ws))
            created += 1
    log(db, user, "entry", "-", "seed", new_value=f"{created} رکورد نمونه",
        reason="بارگذاری داده نمونه")
    db.commit()
    return {"ok": True, "year": year, "created": created}


@router.post("/settings/clear-data")
def settings_clear_data(db: Session = Depends(get_db),
                        user=Depends(require_roles("admin"))):
    """Offline clearData: remove performance entries (KPI definitions kept)."""
    n = db.query(models.KPIEntry).delete()
    log(db, user, "entry", "-", "delete", new_value=f"{n} رکورد حذف شد",
        reason="پاک کردن همه داده‌های عملکرد")
    db.commit()
    return {"ok": True, "deleted": n}
