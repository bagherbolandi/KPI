# -*- coding: utf-8 -*-
"""Strategy module — port of the offline 'اهداف و برنامه‌ها' (strategy) view.

Goals with period ranges, KPI links (improve-vs-baseline / maintain-level),
action plans with numeric start rules, per-goal event history, sample pack,
and the conservative weighted evaluation (progress / expected / freshness).
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..security import get_current_user, require_roles
from ..permissions import can
from ..audit import log
from ..effective import is_due, is_mgt, process_company_map, kpis_of_company

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

ACTION_STATES = ["planned", "in_progress", "blocked", "done"]
RULES = ["always", "behind", "below", "above"]


# ----------------------------------------------------------------- helpers
def period_num(v) -> Optional[int]:
    """'1405/08' -> 1405*12 + 7 (offline strategyPeriod); ints pass through."""
    try:
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v if 1200 * 12 <= v <= 1800 * 12 + 11 else None
        s = str(v).strip()
        y, m = s.split("/")
        y, m = int(y), int(m)
        if y < 1200 or y > 1800 or m < 1 or m > 12:
            return None
        return y * 12 + (m - 1)
    except Exception:
        return None


def period_text(n: int) -> str:
    return f"{n // 12}/{n % 12 + 1:02d}"


def fingerprint(k: models.KPI) -> str:
    return json.dumps([k.direction, k.uom, k.frequency,
                       k.definition or "", k.formula or ""],
                      ensure_ascii=False)


def goal_dict(g: models.StrategyGoal) -> dict:
    return {"id": g.id, "company_id": g.company_id, "title": g.title,
            "description": g.description, "owner_process_code": g.owner_process_code,
            "start": g.start_period, "end": g.end_period,
            "start_text": period_text(g.start_period),
            "end_text": period_text(g.end_period),
            "archived": bool(g.archived), "sample_key": g.sample_key}


def link_dict(l: models.StrategyLink) -> dict:
    return {"id": l.id, "goal_id": l.goal_id, "kpi_id": l.kpi_id,
            "mode": l.mode, "baseline": l.baseline, "target": None,
            "weight": 1.0, "note": "", "fingerprint": None}  # enriched below


def action_dict(a: models.StrategyAction) -> dict:
    return {"id": a.id, "goal_id": a.goal_id, "link_id": a.link_id,
            "title": a.title, "description": a.description,
            "owner_id": a.owner_user_id,
            "owner_name": (a.owner.full_name or a.owner.username) if a.owner else None,
            "due": a.due_period, "due_text": period_text(a.due_period),
            "rule": a.rule, "threshold": a.threshold, "state": a.state,
            "progress": a.progress, "evidence": a.evidence,
            "updated_at": a.updated_at.strftime("%Y-%m-%d %H:%M") if a.updated_at else None}


def event_dict(e: models.StrategyEvent) -> dict:
    try:
        details = json.loads(e.details) if e.details else {}
    except Exception:
        details = {}
    at_fa = None
    if e.at:
        try:
            import jdatetime
            at_fa = jdatetime.datetime.fromgregorian(datetime=e.at).strftime("%Y/%m/%d %H:%M")
            from ..jalali import to_fa_digits
            at_fa = to_fa_digits(at_fa)
        except Exception:
            at_fa = None
    return {"id": e.id, "goal_id": e.goal_id,
            "at": e.at.strftime("%Y-%m-%d %H:%M") if e.at else None,
            "at_fa": at_fa,
            "by": e.by_user_id, "type": e.type, "details": details}


def add_event(db, user, goal_id, etype, details: dict):
    db.add(models.StrategyEvent(goal_id=goal_id, by_user_id=getattr(user, "id", None),
                                type=etype, details=json.dumps(details, ensure_ascii=False,
                                                               default=str)))


# ------------------------------------------------------- evaluation (offline parity)
def measure(db, goal, link, link_extra, asof: int, kpi_map, approved_only=False) -> dict:
    """Offline strategyMeasure for one link at period `asof`."""
    k = kpi_map.get(link.kpi_id)
    frac = max(0.0, min(1.0, (asof - goal.start_period + 1) /
                        max(1, (goal.end_period - goal.start_period + 1))))
    out = {"link": link_dict(link), "kpi_id": link.kpi_id,
           "actual": None, "period": None, "progress": None,
           "expected": frac, "status": "missing",
           "reason": "داده معتبر در دامنه هدف ثبت نشده است.",
           "target": link_extra.get("target"), "weight": link_extra.get("weight", 1.0),
           "note": link_extra.get("note", "")}
    if link.mode == "maintain":
        out["expected"] = 0.0 if asof < goal.start_period else 1.0
    if not k or not k.active:
        out["status"] = "invalid"
        out["reason"] = "شاخص حذف یا غیرفعال شده است؛ اتصال بازنگری شود."
        return out
    if link_extra.get("fingerprint") and link_extra["fingerprint"] != fingerprint(k):
        out["status"] = "invalid"
        out["reason"] = "تعریف، واحد، جهت یا تناوب شاخص تغییر کرده؛ اتصال و خط مبنا بازنگری شود."
        return out
    if asof < goal.start_period:
        out["status"] = "future"
        out["reason"] = "دوره هدف هنوز شروع نشده است."
        return out
    until = min(asof, goal.end_period)
    due = None
    n = goal.start_period
    while n <= until:
        year, month = n // 12, n % 12 + 1
        n += 1
        if not is_due(k.frequency, month):
            continue
        due = n - 1
        if is_mgt(k):
            from ..effective import mgt_actual
            v = mgt_actual(db, year, month, approved_only=approved_only)
        else:
            e = (db.query(models.KPIEntry)
                 .filter_by(kpi_id=k.id, year=year, month=month).first())
            if e is None or e.actual is None:
                continue
            if approved_only and e.workflow_state != "approved":
                continue
            v = e.actual
        if v is not None:
            out["actual"] = v
            out["period"] = n - 1
    if out["actual"] is None:
        if due is None:
            out["status"] = "future"
            out["reason"] = "هنوز دوره پایش این شاخص سررسید نشده است."
        return out
    target = out["target"]
    baseline = link.baseline
    if link.mode == "maintain":
        if target is None:
            out["progress"] = None
        else:
            ok = out["actual"] <= target if k.direction == "down" else out["actual"] >= target
            out["progress"] = 1.0 if ok else 0.0
    else:
        if baseline is None or target is None or target == baseline:
            out["progress"] = None
        else:
            out["progress"] = max(0.0, min(1.0, (out["actual"] - baseline) / (target - baseline)))
    event_driven = k.frequency in ("event", "per_ecn")
    if out["progress"] is None:
        out["reason"] = "خط مبنا یا هدف اتصال تکمیل نشده است."
    elif not event_driven and due is not None and out["period"] < due:
        out["status"] = "stale"
        out["reason"] = "آخرین ثبت قدیمی است؛ دوره پایش جدید فاقد داده معتبر است."
    elif out["progress"] >= 1:
        out["status"] = "achieved"
        out["reason"] = "مقدار هدف محقق شده است."
    elif out["progress"] + 0.1 < out["expected"]:
        out["status"] = "behind"
        out["reason"] = "بیش از ۱۰ واحد درصد از مسیر خطی برنامه عقب است."
    else:
        out["status"] = "ontrack"
        out["reason"] = "در محدوده مسیر برنامه است."
    return out


def evaluate(db, goal, links_extras, asof: int, kpi_map, approved_only=False) -> dict:
    """Offline strategyEvaluate: conservative weighted rollup."""
    rows = [measure(db, goal, le["_obj"], le, asof, kpi_map, approved_only)
            for le in links_extras]
    weight = known = ssum = fresh = 0.0
    exp_sum = 0.0
    for r in rows:
        w = r["weight"] or 1.0
        weight += w
        if r["progress"] is not None:
            known += w
            ssum += r["progress"] * w
        if r["status"] in ("ontrack", "behind", "achieved"):
            fresh += w
        exp_sum += r["expected"] * w
    progress = (ssum / weight) if weight else None
    if weight:
        expected = exp_sum / weight
    else:
        expected = max(0.0, min(1.0, (asof - goal.start_period + 1) /
                                max(1, (goal.end_period - goal.start_period + 1))))
    if goal.archived:
        status = "بایگانی"
    elif not rows:
        status = "بدون شاخص مرتبط"
    elif asof < goal.start_period:
        status = "شروع نشده"
    elif fresh < weight:
        status = "نیازمند تکمیل یا بازنگری داده"
    elif progress is not None and progress >= 1:
        status = "محقق‌شده"
    elif progress is not None and progress + 0.1 < expected:
        status = "عقب از برنامه"
    else:
        status = "در مسیر"
    return {"rows": rows, "progress": progress,
            "coverage": (known / weight) if weight else 0,
            "freshness": (fresh / weight) if weight else 0,
            "expected": expected, "status": status}


def trigger(db, goal, action, asof: int, kpi_map, links_extras, approved_only=False) -> dict:
    """Offline strategyTrigger: numeric start-rule suggestion for an action."""
    if goal.archived or asof < goal.start_period:
        return {"active": False, "reason": "هدف فعال نیست یا هنوز شروع نشده است."}
    if action.rule == "always":
        return {"active": True, "reason": "اقدام برنامه‌ریزی‌شده"}
    ev = evaluate(db, goal, links_extras, asof, kpi_map, approved_only)
    row = next((r for r in ev["rows"] if r["link"]["id"] == action.link_id), None)
    if not row or row["status"] not in ("ontrack", "behind", "achieved"):
        return {"active": False, "reason": "برای تصمیم، داده تازه و اتصال معتبر لازم است."}
    k = kpi_map.get(row["kpi_id"])
    code = k.code if k else "?"
    if action.rule == "behind":
        active = row["status"] == "behind"
    elif action.rule == "below":
        active = row["actual"] is not None and action.threshold is not None and row["actual"] < action.threshold
    else:  # above
        active = row["actual"] is not None and action.threshold is not None and row["actual"] > action.threshold
    label = f"{code} = {row['actual']} ({period_text(row['period'])})" if row["period"] else code
    return {"active": active,
            "reason": ("شرط برقرار است؛ " if active else "شرط برقرار نیست؛ ") + label}


# ----------------------------------------------------------------- endpoints
def _load_goal(db, gid) -> models.StrategyGoal:
    g = db.get(models.StrategyGoal, gid)
    if not g:
        raise HTTPException(404, "هدف یافت نشد")
    return g


def _links_extras(db, goal) -> list:
    """Links enriched with the JSON snapshot (target/weight/note/fingerprint)."""
    out = []
    for l in goal_links(db, goal):
        extra = {"target": None, "weight": 1.0, "note": "", "fingerprint": None}
        try:
            snap = json.loads(l.snapshot) if getattr(l, "snapshot", None) else {}
            extra.update({k: snap.get(k, extra[k]) for k in extra})
        except Exception:
            pass
        extra["_obj"] = l
        out.append(extra)
    return out


def goal_links(db, goal):
    return db.query(models.StrategyLink).filter_by(goal_id=goal.id).all()


def now_period() -> int:
    """جاری: شماره دوره ماه جاری (سال*۱۲ + ماه-۱) — پیش‌فرض ارزیابی."""
    from ..jalali import today as _t
    t = _t()
    return t["year"] * 12 + (t["month"] - 1)


def default_company_id(db) -> Optional[int]:
    """First company by display order — used when the caller omits company_id."""
    c = (db.query(models.OrgUnit).filter_by(level="company")
         .order_by(models.OrgUnit.order).first())
    return c.id if c else None


@router.get("/goals")
def list_goals(company_id: int | None = Query(None), asof: Optional[int] = None,
               include_archived: bool = True,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    company_id = company_id or default_company_id(db)
    q = db.query(models.StrategyGoal).filter(models.StrategyGoal.company_id == company_id)
    if not include_archived:
        q = q.filter(models.StrategyGoal.archived == False)  # noqa: E712
    goals = q.order_by(models.StrategyGoal.id).all()
    kpi_map = {k.id: k for k in db.query(models.KPI).all()}
    out = []
    aof = asof if asof is not None else now_period()
    for g in goals:
        extras = _links_extras(db, g)
        ev = evaluate(db, g, extras, aof, kpi_map)
        rows = (db.query(models.StrategyAction).filter_by(goal_id=g.id)
                .order_by(models.StrategyAction.id).all())
        actions = []
        for a in rows:
            ad = action_dict(a)
            ad["trigger"] = trigger(db, g, a, aof, kpi_map, extras)
            actions.append(ad)
        events = [event_dict(e) for e in
                  db.query(models.StrategyEvent).filter_by(goal_id=g.id)
                  .order_by(models.StrategyEvent.id.desc()).limit(50).all()]
        out.append({**goal_dict(g), "evaluation": _clean_eval(ev),
                    "links": [_clean_row(r) for r in ev["rows"]],
                    "actions": actions, "events": events})
    return {"company_id": company_id, "goals": out, "asof": aof,
            "asof_text": period_text(aof)}


def _clean_eval(ev: dict) -> dict:
    return {"progress": ev["progress"], "expected": ev["expected"],
            "coverage": ev["coverage"], "freshness": ev["freshness"],
            "status": ev["status"]}


def _clean_row(r: dict) -> dict:
    k = r.get("kpi_id")
    from ..jalali import label
    period = r["period"]
    return {"link": r["link"], "kpi_id": k, "actual": r["actual"],
            "period": period,
            "period_text": period_text(period) if period is not None else None,
            "progress": r["progress"], "expected": r["expected"],
            "status": r["status"], "reason": r["reason"],
            "target": r["target"], "weight": r["weight"], "note": r["note"]}


def _require_edit(user):
    if not can(user, "master"):
        raise HTTPException(403, "برای ویرایش اهداف، دسترسی «مدیریت شاخص‌ها» لازم است")


@router.post("/goals")
def create_goal(body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_edit(user)
    title = str(body.get("title", "")).strip()
    company_id = body.get("company_id") or default_company_id(db)
    proc = str(body.get("owner_process_code", "")).strip()
    # API clients may send either start/end or start_period/end_period
    start = period_num(body.get("start", body.get("start_period")))
    end = period_num(body.get("end", body.get("end_period")))
    if not title:
        raise HTTPException(400, "عنوان هدف الزامی است")
    if not company_id or not db.get(models.OrgUnit, company_id):
        raise HTTPException(400, "شرکت نامعتبر است")
    procs = {p.code for p in db.query(models.OrgUnit).filter_by(level="process")}
    if proc not in procs:
        raise HTTPException(400, "فرایند پاسخ‌گوی معتبر انتخاب کنید")
    if start is None or end is None or end < start or end - start >= 240:
        raise HTTPException(400, "دامنه هدف باید معتبر، مرتب و حداکثر ۲۰ سال باشد (۱۴۰۵/۰۱)")
    g = models.StrategyGoal(company_id=company_id, title=title,
                            description=str(body.get("description", "")).strip(),
                            owner_process_code=proc, start_period=start, end_period=end)
    db.add(g); db.flush()
    add_event(db, user, g.id, "ایجاد هدف", {"after": goal_dict(g)})
    log(db, user, "strategy", g.id, "create", new_value=title)
    db.commit()
    return goal_dict(g)


@router.put("/goals/{gid}")
def update_goal(gid: int, body: dict, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    _require_edit(user)
    g = _load_goal(db, gid)
    title = str(body.get("title", g.title)).strip()
    proc = str(body.get("owner_process_code", g.owner_process_code)).strip()
    start = period_num(body.get("start", body.get(
        "start_period", period_text(g.start_period))))
    end = period_num(body.get("end", body.get(
        "end_period", period_text(g.end_period))))
    if not title:
        raise HTTPException(400, "عنوان هدف الزامی است")
    procs = {p.code for p in db.query(models.OrgUnit).filter_by(level="process")}
    if proc not in procs:
        raise HTTPException(400, "فرایند پاسخ‌گوی معتبر انتخاب کنید")
    if start is None or end is None or end < start or end - start >= 240:
        raise HTTPException(400, "دامنه هدف باید معتبر، مرتب و حداکثر ۲۰ سال باشد (۱۴۰۵/۰۱)")
    acts = db.query(models.StrategyAction).filter_by(goal_id=g.id).all()
    if any(a.due_period < start or a.due_period > end for a in acts):
        raise HTTPException(400, "ابتدا سررسید برنامه‌های اقدام را با دامنه جدید هماهنگ کنید")
    before = goal_dict(g)
    g.title = title
    g.description = str(body.get("description", g.description)).strip()
    g.owner_process_code = proc
    g.start_period = start
    g.end_period = end
    add_event(db, user, g.id, "ویرایش هدف", {"before": before, "after": goal_dict(g)})
    log(db, user, "strategy", g.id, "update", field="title", old_value=before["title"],
        new_value=title)
    db.commit()
    return goal_dict(g)


@router.post("/goals/{gid}/archive")
def archive_goal(gid: int, db: Session = Depends(get_db),
                 user=Depends(get_current_user)):
    _require_edit(user)
    g = _load_goal(db, gid)
    g.archived = not g.archived
    add_event(db, user, g.id, "بایگانی هدف" if g.archived else "فعال‌سازی هدف", {})
    log(db, user, "strategy", g.id, "update", field="archived",
        new_value=str(g.archived))
    db.commit()
    return goal_dict(g)


# ------------------------------------------------------------------ links
@router.post("/goals/{gid}/links")
def create_link(gid: int, body: dict, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    _require_edit(user)
    g = _load_goal(db, gid)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده و قابل ویرایش نیست")
    kpi_id = body.get("kpi_id")
    k = db.get(models.KPI, kpi_id)
    if not k:
        raise HTTPException(400, "شاخص نامعتبر است")
    mode = body.get("mode", "improve")
    if mode not in ("improve", "maintain"):
        raise HTTPException(400, "روش ارزیابی نامعتبر است")
    baseline = body.get("baseline")
    target = body.get("target")
    weight = body.get("weight", 1)
    try:
        weight = float(weight)
    except Exception:
        weight = 1.0
    if weight <= 0:
        raise HTTPException(400, "وزن اتصال باید بزرگ‌تر از صفر باشد")
    if mode == "improve" and (baseline is None or target is None):
        raise HTTPException(400, "در حالت بهبود، خط مبنا و هدف الزامی است")
    if target is None:
        raise HTTPException(400, "مقدار هدف استراتژیک الزامی است")
    if mode == "improve" and float(target) == float(baseline or 0):
        raise HTTPException(400, "هدف با خط مبنا نمی‌تواند یکسان باشد")
    l = models.StrategyLink(goal_id=g.id, kpi_id=k.id, mode=mode,
                            baseline=float(baseline) if baseline is not None else None)
    l.snapshot = json.dumps({"target": float(target), "weight": weight,
                             "note": str(body.get("note", "")),
                             "fingerprint": fingerprint(k)}, ensure_ascii=False)
    db.add(l); db.flush()
    add_event(db, user, g.id, "ذخیره اتصال",
              {"after": {"kpi_id": k.id, "mode": mode, "target": target}})
    log(db, user, "strategy", g.id, "create", field="link", new_value=k.code)
    db.commit()
    return {"id": l.id}


@router.put("/links/{lid}")
def update_link(lid: int, body: dict, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    _require_edit(user)
    l = db.get(models.StrategyLink, lid)
    if not l:
        raise HTTPException(404, "اتصال یافت نشد")
    g = _load_goal(db, l.goal_id)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده و قابل ویرایش نیست")
    if body.get("kpi_id") is not None and int(body["kpi_id"]) != l.kpi_id:
        used = db.query(models.StrategyAction).filter_by(link_id=l.id).count()
        if used:
            raise HTTPException(400, "برای اتصال دارای برنامه اقدام، شاخص را عوض نکنید؛ اتصال جدید بسازید")
        k = db.get(models.KPI, int(body["kpi_id"]))
        if not k:
            raise HTTPException(400, "شاخص نامعتبر است")
        l.kpi_id = k.id
    k = db.get(models.KPI, l.kpi_id)
    mode = body.get("mode", l.mode)
    if mode not in ("improve", "maintain"):
        raise HTTPException(400, "روش ارزیابی نامعتبر است")
    baseline = body.get("baseline", l.baseline)
    target = body.get("target")
    weight = body.get("weight", 1)
    try:
        weight = float(weight)
    except Exception:
        weight = 1.0
    if weight <= 0:
        raise HTTPException(400, "وزن اتصال باید بزرگ‌تر از صفر باشد")
    if mode == "improve" and (baseline is None or target is None):
        raise HTTPException(400, "در حالت بهبود، خط مبنا و هدف الزامی است")
    if target is None:
        raise HTTPException(400, "مقدار هدف استراتژیک الزامی است")
    l.mode = mode
    l.baseline = float(baseline) if baseline is not None else None
    l.snapshot = json.dumps({"target": float(target), "weight": weight,
                             "note": str(body.get("note", "")),
                             "fingerprint": fingerprint(k)}, ensure_ascii=False)
    add_event(db, user, g.id, "ویرایش اتصال", {"after": {"kpi_id": l.kpi_id, "mode": mode}})
    log(db, user, "strategy", g.id, "update", field="link", new_value=k.code if k else "")
    db.commit()
    return {"id": l.id}


@router.delete("/links/{lid}")
def delete_link(lid: int, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    _require_edit(user)
    l = db.get(models.StrategyLink, lid)
    if not l:
        raise HTTPException(404, "اتصال یافت نشد")
    g = _load_goal(db, l.goal_id)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده و قابل ویرایش نیست")
    if db.query(models.StrategyAction).filter_by(link_id=lid).count():
        raise HTTPException(400, "این اتصال برنامه اقدام دارد و قابل حذف نیست")
    db.delete(l)
    add_event(db, user, g.id, "حذف اتصال", {"kpi_id": l.kpi_id})
    log(db, user, "strategy", g.id, "delete", field="link")
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- actions
@router.post("/goals/{gid}/actions")
def create_action(gid: int, body: dict, db: Session = Depends(get_db),
                  user=Depends(get_current_user)):
    _require_edit(user)
    g = _load_goal(db, gid)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده و قابل ویرایش نیست")
    title = str(body.get("title", "")).strip()
    due = period_num(body.get("due"))
    rule = body.get("rule", "always")
    if not title:
        raise HTTPException(400, "عنوان اقدام الزامی است")
    if due is None or due < g.start_period or due > g.end_period:
        raise HTTPException(400, "سررسید اقدام باید داخل دامنه هدف باشد")
    if rule not in RULES:
        raise HTTPException(400, "شرط شروع نامعتبر است")
    link_id = body.get("link_id") or None
    if link_id:
        l = db.get(models.StrategyLink, int(link_id))
        if not l or l.goal_id != g.id:
            raise HTTPException(400, "اتصال نامعتبر است")
    threshold = body.get("threshold")
    a = models.StrategyAction(
        goal_id=g.id, link_id=int(link_id) if link_id else None,
        title=title, description=str(body.get("description", "")).strip(),
        owner_user_id=int(body["owner_id"]) if body.get("owner_id") else getattr(user, "id", None),
        due_period=due, rule=rule,
        threshold=float(threshold) if threshold not in (None, "") else None,
        state=body.get("state", "planned") if body.get("state") in ACTION_STATES else "planned",
        progress=float(body.get("progress") or 0),
        evidence=str(body.get("evidence", "")).strip())
    db.add(a); db.flush()
    add_event(db, user, g.id, "ایجاد برنامه اقدام", {"actionId": a.id, "title": title})
    log(db, user, "strategy", g.id, "create", field="action", new_value=title)
    db.commit()
    return {"id": a.id}


@router.put("/actions/{aid}")
def update_action(aid: int, body: dict, db: Session = Depends(get_db),
                  user=Depends(get_current_user)):
    a = db.get(models.StrategyAction, aid)
    if not a:
        raise HTTPException(404, "اقدام یافت نشد")
    g = _load_goal(db, a.goal_id)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده و قابل ویرایش نیست")
    _require_edit(user)
    title = str(body.get("title", a.title)).strip()
    due = period_num(body.get("due", period_text(a.due_period)))
    rule = body.get("rule", a.rule)
    if not title:
        raise HTTPException(400, "عنوان اقدام الزامی است")
    if due is None or due < g.start_period or due > g.end_period:
        raise HTTPException(400, "سررسید اقدام باید داخل دامنه هدف باشد")
    if rule not in RULES:
        raise HTTPException(400, "شرط شروع نامعتبر است")
    if "state" in body and body["state"] not in ACTION_STATES:
        raise HTTPException(400, "وضعیت نامعتبر است")
    a.title = title
    a.description = str(body.get("description", a.description)).strip()
    a.due_period = due
    a.rule = rule
    if "threshold" in body:
        a.threshold = float(body["threshold"]) if body["threshold"] not in (None, "") else None
    if "owner_id" in body:
        a.owner_user_id = int(body["owner_id"]) if body["owner_id"] else None
    add_event(db, user, g.id, "ویرایش برنامه اقدام", {"actionId": a.id, "title": title})
    log(db, user, "strategy", g.id, "update", field="action", new_value=title)
    db.commit()
    return action_dict(a)


@router.post("/actions/{aid}/report")
def report_action(aid: int, body: dict, db: Session = Depends(get_db),
                  user=Depends(get_current_user)):
    """State/progress/evidence report (offline strategyUpdateAction)."""
    a = db.get(models.StrategyAction, aid)
    if not a:
        raise HTTPException(404, "اقدام یافت نشد")
    g = _load_goal(db, a.goal_id)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده و قابل ویرایش نیست")
    _require_edit(user)
    st = body.get("state")
    progress = body.get("progress")
    evidence = str(body.get("evidence", "")).strip()
    if st not in ACTION_STATES:
        raise HTTPException(400, "وضعیت نامعتبر است")
    try:
        progress = float(progress)
    except Exception:
        progress = -1
    if progress < 0 or progress > 100:
        raise HTTPException(400, "پیشرفت باید بین صفر و صد باشد")
    if not evidence:
        raise HTTPException(400, "گزارش اجرا یا دلیل تغییر وضعیت را ثبت کنید")
    if st == "done" and progress != 100:
        raise HTTPException(400, "برای تکمیل، پیشرفت کار باید ۱۰۰٪ باشد")
    if st == "planned" and progress != 0:
        raise HTTPException(400, "اقدام شروع‌نشده باید پیشرفت صفر داشته باشد")
    before = {"state": a.state, "progress": a.progress}
    a.state = st
    a.progress = progress
    a.evidence = evidence
    add_event(db, user, g.id, "گزارش اجرای اقدام",
              {"actionId": a.id, "before": before, "after": {"state": st, "progress": progress}})
    log(db, user, "strategy", g.id, "update", field="action_state",
        old_value=before["state"], new_value=st)
    db.commit()
    return action_dict(a)


@router.post("/actions/{aid}/start-checked")
def start_action_checked(aid: int, body: dict, db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    """Start an action only if its numeric rule fires at `asof` (offline strategyStartAction)."""
    a = db.get(models.StrategyAction, aid)
    if not a:
        raise HTTPException(404, "اقدام یافت نشد")
    g = _load_goal(db, a.goal_id)
    if g.archived:
        raise HTTPException(400, "هدف بایگانی شده است")
    _require_edit(user)
    if a.state != "planned":
        raise HTTPException(400, "فقط اقدام برنامه‌ریزی‌شده قابل شروع است")
    asof = period_num(body.get("asof")) or g.end_period
    kpi_map = {k.id: k for k in db.query(models.KPI).all()}
    extras = _links_extras(db, g)
    t = trigger(db, g, a, asof, kpi_map, extras)
    if not t["active"]:
        raise HTTPException(400, t["reason"])
    a.state = "in_progress"
    add_event(db, user, g.id, "شروع اقدام",
              {"actionId": a.id, "reason": t["reason"], "asof": asof})
    log(db, user, "strategy", g.id, "update", field="action_state",
        old_value="planned", new_value="in_progress", reason=t["reason"])
    db.commit()
    return action_dict(a)


# ---------------------------------------------------------------- samples
SAMPLE_TEMPLATES = [
    {"key": "production", "title": "پایداری تولید و افزایش بهره‌وری تجهیزات",
     "process": "PLN", "codes": ["PLN-01", "PLN-02", "PLN-04"],
     "description": "نمونه پیشنهادی: تحقق برنامه تولید، افزایش بهره‌وری پرس و مهار توقفات برنامه‌ریزی."},
    {"key": "quality", "title": "کاهش عدم انطباق و تقویت اثربخشی اقدامات اصلاحی",
     "process": "QA", "codes": ["QC-01", "QC-07", "QA-03"],
     "description": "نمونه پیشنهادی: کنترل PPM مشتری، کاهش دوباره‌کاری و بستن به‌موقع اقدامات اصلاحی."},
    {"key": "supply", "title": "پایداری تأمین و کاهش ریسک کمبود مواد",
     "process": "PUR", "codes": ["PUR-03", "PUR-05", "PLN-10"],
     "description": "نمونه پیشنهادی: کاهش تأخیر تأمین‌کنندگان، ارزیابی آن‌ها و کنترل کمبود مواد اولیه."},
    {"key": "customer", "title": "افزایش رضایت مشتری و قابلیت اتکای تحویل",
     "process": "SAL", "codes": ["SAL-01", "SAL-05", "SAL-09"],
     "description": "نمونه پیشنهادی: حفظ رضایت مشتری، دستیابی به امتیاز تحویل و رسیدگی به‌موقع به شکایت‌ها."},
]


@router.post("/samples")
def install_samples(body: dict, db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    _require_edit(user)
    company_id = body.get("company_id") or default_company_id(db)
    from ..jalali import today as _today
    year = int(body.get("year") or _today()["year"])
    if not company_id or not db.get(models.OrgUnit, company_id):
        raise HTTPException(400, "شرکت نامعتبر است")
    proc_codes = {p.code for p in db.query(models.OrgUnit).filter_by(level="process")}
    kpis = db.query(models.KPI).filter(models.KPI.active == True).all()  # noqa
    by_code = {k.code: k for k in kpis}
    created = linked = 0
    skipped = []
    for t in SAMPLE_TEMPLATES:
        existing = (db.query(models.StrategyGoal)
                    .filter_by(company_id=company_id, sample_key="v1:" + t["key"]).first())
        if existing:
            continue
        ks = [by_code[c] for c in t["codes"] if c in by_code and not is_mgt(by_code[c])]
        if not ks:
            skipped.append(t["title"])
            continue
        proc = t["process"] if t["process"] in proc_codes else ks[0].process.code
        if proc not in proc_codes:
            skipped.append(t["title"])
            continue
        g = models.StrategyGoal(
            company_id=company_id, title=t["title"] + " (نمونه)",
            description=t["description"] +
            " اهداف عددی از تنظیم فعلی شاخص‌ها کپی شده‌اند و پیش از استفاده اجرایی باید بازنگری شوند.",
            owner_process_code=proc, start_period=year * 12,
            end_period=year * 12 + 11, sample_key="v1:" + t["key"])
        db.add(g); db.flush()
        for k in ks:
            l = models.StrategyLink(goal_id=g.id, kpi_id=k.id, mode="maintain",
                                    baseline=None)
            l.snapshot = json.dumps(
                {"target": k.target, "weight": 1.0,
                 "note": "نمونه: آستانه از هدف فعلی شاخص گرفته شده؛ وزن برابر پیشنهادی است.",
                 "fingerprint": fingerprint(k)}, ensure_ascii=False)
            db.add(l)
            linked += 1
        add_event(db, user, g.id, "ایجاد هدف نمونه", {"after": goal_dict(g)})
        created += 1
    log(db, user, "strategy", "-", "create", field="samples",
        new_value=f"{created} هدف نمونه")
    db.commit()
    return {"created": created, "linked": linked, "skipped": skipped}
