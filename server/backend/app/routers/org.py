# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..schemas import OrgIn
from ..security import get_current_user, require_roles
from ..audit import log

router = APIRouter(prefix="/api/org", tags=["org"])


def node_dict(n: models.OrgUnit, kpi_counts: dict):
    return {"id": n.id, "code": n.code, "name": n.name, "level": n.level,
            "parent_id": n.parent_id, "owner_user_id": n.owner_user_id,
            "kpi_count": kpi_counts.get(n.id, 0)}


@router.get("/tree")
def tree(db: Session = Depends(get_db), user=Depends(get_current_user)):
    units = db.query(models.OrgUnit).order_by(models.OrgUnit.order).all()
    # count kpis per process
    from sqlalchemy import func
    counts = dict(db.query(models.KPI.process_id, func.count(models.KPI.id))
                  .group_by(models.KPI.process_id).all())
    by_parent = {}
    nodes = {u.id: node_dict(u, counts) for u in units}
    for u in units:
        by_parent.setdefault(u.parent_id, []).append(nodes[u.id])
    # roll up kpi counts to divisions/company
    def rollup(node):
        kids = by_parent.get(node["id"], [])
        node["children"] = kids
        total = node["kpi_count"]
        for c in kids:
            total += rollup(c)
        node["total_kpis"] = total
        return total
    roots = by_parent.get(None, [])
    for r in roots:
        rollup(r)
    return roots


@router.get("/processes")
def processes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    procs = (db.query(models.OrgUnit)
             .filter(models.OrgUnit.level == "process")
             .order_by(models.OrgUnit.order).all())
    out = []
    for p in procs:
        owner = db.get(models.User, p.owner_user_id) if p.owner_user_id else None
        div = db.get(models.OrgUnit, p.parent_id)
        out.append({"id": p.id, "code": p.code, "name": p.name,
                    "division": div.name if div else None,
                    "owner": owner.full_name if owner else None})
    return out


@router.post("/units")
def create_unit(body: OrgIn, db: Session = Depends(get_db),
                user=Depends(require_roles("admin"))):
    n = models.OrgUnit(code=body.code, name=body.name, level=body.level,
                       parent_id=body.parent_id, owner_user_id=body.owner_user_id)
    db.add(n); db.flush()
    log(db, user, "org", n.id, "create", new_value=body.name)
    db.commit()
    return {"id": n.id}


@router.put("/units/{uid}")
def update_unit(uid: int, body: OrgIn, db: Session = Depends(get_db),
                user=Depends(require_roles("admin"))):
    n = db.get(models.OrgUnit, uid)
    if not n:
        raise HTTPException(404, "یافت نشد")
    old = n.name
    n.name = body.name; n.code = body.code
    n.owner_user_id = body.owner_user_id; n.parent_id = body.parent_id
    log(db, user, "org", n.id, "update", field="name", old_value=old, new_value=body.name)
    db.commit()
    return {"ok": True}
