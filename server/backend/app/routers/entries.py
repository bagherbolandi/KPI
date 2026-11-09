# -*- coding: utf-8 -*-
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..schemas import EntryIn, WorkflowAction
from ..security import get_current_user, require_roles
from ..calc import evaluate
from ..settings_util import get_thresholds
from ..audit import log
from ..jalali import label

router = APIRouter(prefix="/api/entries", tags=["entries"])

# workflow transitions and who may perform them
TRANSITIONS = {
    "submit":  {"from": ["draft", "rejected"], "to": "submitted",  "roles": ["process_owner", "admin"]},
    "review":  {"from": ["submitted"],         "to": "qc_reviewed", "roles": ["quality", "admin"]},
    "approve": {"from": ["qc_reviewed", "submitted"], "to": "approved", "roles": ["quality", "admin"]},
    "reject":  {"from": ["submitted", "qc_reviewed"], "to": "rejected", "roles": ["quality", "admin"]},
    "reopen":  {"from": ["approved", "rejected"], "to": "draft",    "roles": ["admin"]},
}


def entry_dict(e: models.KPIEntry, k: models.KPI):
    return {
        "id": e.id, "kpi_id": e.kpi_id, "kpi_code": k.code, "kpi_name": k.name,
        "uom": k.uom, "direction": k.direction, "target": k.target,
        "year": e.year, "month": e.month, "period": label(e.year, e.month),
        "actual": e.actual, "achievement": e.achievement, "status": e.status,
        "comment": e.comment, "deviation_cause": e.deviation_cause,
        "corrective_action": e.corrective_action, "workflow_state": e.workflow_state,
        "rejection_reason": e.rejection_reason,
    }


@router.get("")
def list_entries(kpi_id: int | None = None, process_id: int | None = None,
                 year: int | None = None, month: int | None = None,
                 state: str | None = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(models.KPIEntry).join(models.KPI)
    if user.role.code == "process_owner" and user.process_id:
        q = q.filter(models.KPI.process_id == user.process_id)
    elif process_id:
        q = q.filter(models.KPI.process_id == process_id)
    if kpi_id:
        q = q.filter(models.KPIEntry.kpi_id == kpi_id)
    if year:
        q = q.filter(models.KPIEntry.year == year)
    if month:
        q = q.filter(models.KPIEntry.month == month)
    if state:
        q = q.filter(models.KPIEntry.workflow_state == state)
    rows = q.order_by(models.KPIEntry.year.desc(), models.KPIEntry.month.desc()).all()
    return [entry_dict(e, e.kpi) for e in rows]


@router.post("")
def upsert_entry(body: EntryIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    k = db.get(models.KPI, body.kpi_id)
    if not k:
        raise HTTPException(404, "شاخص یافت نشد")
    if user.role.code == "process_owner" and user.process_id != k.process_id:
        raise HTTPException(403, "شما تنها مجاز به ثبت داده فرایند خود هستید")
    if user.role.code == "executive":
        raise HTTPException(403, "مدیریت ارشد دسترسی ثبت داده ندارد")

    e = (db.query(models.KPIEntry)
         .filter_by(kpi_id=body.kpi_id, year=body.year, month=body.month).first())
    tg, ty = get_thresholds(db)
    ach, st = evaluate(k, body.actual, tg, ty)
    created = False
    if not e:
        e = models.KPIEntry(kpi_id=body.kpi_id, year=body.year, month=body.month)
        db.add(e); created = True
    if e.workflow_state == "approved" and user.role.code != "admin":
        raise HTTPException(400, "این رکورد تأیید نهایی شده و قابل ویرایش نیست")
    old_actual = e.actual
    e.actual = body.actual; e.achievement = ach; e.status = st
    e.comment = body.comment; e.deviation_cause = body.deviation_cause
    e.corrective_action = body.corrective_action
    if e.workflow_state in ("rejected", "approved"):
        e.workflow_state = "draft"
    log(db, user, "entry", e.id, "create" if created else "update",
        field="actual", old_value=old_actual, new_value=body.actual)
    db.commit()
    return entry_dict(e, k)


@router.post("/workflow")
def workflow(body: WorkflowAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = db.get(models.KPIEntry, body.entry_id)
    if not e:
        raise HTTPException(404, "رکورد یافت نشد")
    k = db.get(models.KPI, e.kpi_id)
    tr = TRANSITIONS.get(body.action)
    if not tr:
        raise HTTPException(400, "عملیات نامعتبر")
    if user.role.code not in tr["roles"]:
        raise HTTPException(403, "شما مجاز به این اقدام نیستید")
    if user.role.code == "process_owner" and user.process_id != k.process_id:
        raise HTTPException(403, "دسترسی به فرایند دیگر مجاز نیست")
    if e.workflow_state not in tr["from"]:
        raise HTTPException(400, f"انتقال از وضعیت «{e.workflow_state}» مجاز نیست")
    now = datetime.utcnow()
    e.workflow_state = tr["to"]
    if body.action == "submit":
        e.submitted_by = user.id; e.submitted_at = now
    elif body.action == "review":
        e.reviewed_by = user.id; e.reviewed_at = now
    elif body.action == "approve":
        e.approved_by = user.id; e.approved_at = now
    elif body.action == "reject":
        e.rejection_reason = body.reason
    log(db, user, "entry", e.id, body.action, new_value=tr["to"], reason=body.reason)
    db.commit()
    return entry_dict(e, k)


@router.get("/inbox")
def inbox(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Pending items requiring the current user's action."""
    q = db.query(models.KPIEntry).join(models.KPI)
    if user.role.code == "quality":
        q = q.filter(models.KPIEntry.workflow_state.in_(["submitted", "qc_reviewed"]))
    elif user.role.code == "process_owner":
        q = q.filter(models.KPI.process_id == user.process_id,
                     models.KPIEntry.workflow_state.in_(["draft", "rejected"]))
    elif user.role.code == "admin":
        q = q.filter(models.KPIEntry.workflow_state.in_(["submitted", "qc_reviewed"]))
    else:
        return []
    rows = q.order_by(models.KPIEntry.year.desc(), models.KPIEntry.month.desc()).limit(200).all()
    return [entry_dict(e, e.kpi) for e in rows]
