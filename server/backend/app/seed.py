# -*- coding: utf-8 -*-
import json
from sqlalchemy.orm import Session
from . import models
from .database import Base, engine, SessionLocal
from .config import SEED_FILE, DEFAULT_TH_GREEN, DEFAULT_TH_YELLOW
from .security import hash_password
from .calc import evaluate

ROLES = [
    ("admin", "مدیر سیستم", "Administrator", "دسترسی کامل به همه بخش‌ها، مدیریت کاربران، شاخص‌ها و ساختار سازمانی"),
    ("process_owner", "مالک فرایند", "Process Owner", "ثبت عملکرد و اقدامات اصلاحی فرایند خود"),
    ("quality", "مدیر کیفیت", "Quality Manager", "پایش همه فرایندها، بررسی و تأیید داده‌ها، گزارش‌گیری"),
    ("executive", "مدیریت ارشد", "Executive", "مشاهده داشبورد کلان و شاخص‌های استراتژیک"),
]

# division code -> friendly name is embedded in seed rows (division_name)
PROC_NAMES = {}  # code -> persian name


def _clear_and_create():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def run_seed():
    _clear_and_create()
    data = json.load(open(SEED_FILE, encoding="utf-8"))
    kpis = data["kpis"]
    entries = data["entries"]
    db: Session = SessionLocal()
    try:
        # ---- roles ----
        role_by_code = {}
        for code, fa, en, desc in ROLES:
            r = models.Role(code=code, name_fa=fa, name_en=en, description=desc)
            db.add(r); db.flush(); role_by_code[code] = r

        # ---- settings ----
        db.add(models.Setting(key="th_green", value=str(DEFAULT_TH_GREEN)))
        db.add(models.Setting(key="th_yellow", value=str(DEFAULT_TH_YELLOW)))
        db.add(models.Setting(key="org_name", value="شرکت صنعتی نمونه (پارس‌قطعه)"))
        db.add(models.Setting(key="current_year", value="1405"))

        # ---- org tree: company -> divisions -> processes ----
        company = models.OrgUnit(code="CO", name="شرکت صنعتی نمونه (پارس‌قطعه)", level="company", order=0)
        db.add(company); db.flush()

        # collect divisions & processes preserving order of appearance
        div_by_code = {}
        proc_by_code = {}
        div_order = 0
        proc_order = 0
        for k in kpis:
            dc = k["division_code"]; dn = k["division_name"]
            if dc not in div_by_code:
                div_order += 1
                d = models.OrgUnit(code=dc, name=dn, level="division",
                                   parent_id=company.id, order=div_order)
                db.add(d); db.flush(); div_by_code[dc] = d
            pc = k["process_code"]; pn = k["process_name"]
            if pc not in proc_by_code:
                proc_order += 1
                p = models.OrgUnit(code=pc, name=pn, level="process",
                                   parent_id=div_by_code[dc].id, order=proc_order)
                db.add(p); db.flush(); proc_by_code[pc] = p
                PROC_NAMES[pc] = pn

        # ---- users ----
        def mkuser(username, full, role, proc=None):
            u = models.User(username=username, full_name=full,
                            email=f"{username}@parsqoteh.ir",
                            hashed_password=hash_password("Passw0rd!"),
                            role_id=role_by_code[role].id,
                            process_id=proc.id if proc else None)
            db.add(u); db.flush(); return u

        admin = mkuser("admin", "مدیر سیستم", "admin")
        exec_u = mkuser("ceo", "دکتر رضایی (مدیرعامل)", "executive")
        qm = mkuser("quality", "مهندس کریمی (مدیر تضمین کیفیت)", "quality")

        # one process owner per process
        owners = {}
        owner_names = ["مهندس احمدی", "مهندس محمدی", "مهندس حسینی", "مهندس رحیمی",
                       "مهندس موسوی", "مهندس نجفی", "مهندس صادقی", "مهندس یوسفی",
                       "مهندس کاظمی", "مهندس جعفری", "مهندس عباسی", "مهندس فتحی",
                       "مهندس بابایی", "مهندس قاسمی", "مهندس شریفی", "مهندس اکبری"]
        for i, (pc, p) in enumerate(proc_by_code.items()):
            uname = f"owner_{pc.lower()}"
            o = mkuser(uname, f"{owner_names[i % len(owner_names)]} ({p.name})", "process_owner", p)
            owners[pc] = o
            p.owner_user_id = o.id
        db.flush()

        # ---- KPIs ----
        th_g, th_y = DEFAULT_TH_GREEN, DEFAULT_TH_YELLOW
        kpi_by_code = {}
        for k in kpis:
            proc = proc_by_code[k["process_code"]]
            owner = owners.get(k["process_code"])
            obj = models.KPI(
                code=k["code"], name=k["name"], process_id=proc.id,
                uom=k["uom"], direction=k["direction"], frequency=k["frequency"],
                target=k["target"], warning=k["warning"], critical=k["critical"],
                weight=k["weight"], importance=k["importance"], is_strategic=k["is_strategic"],
                definition=k["definition"], formula=k["formula"],
                acceptance_text=k["acceptance_text"], calc_mode="achievement",
                data_owner_id=owner.id if owner else None,
                approver_id=qm.id, active=True,
            )
            db.add(obj); db.flush(); kpi_by_code[k["code"]] = obj

        # ---- entries with computed achievement/status ----
        for e in entries:
            kpi = kpi_by_code.get(e["kpi_code"])
            if not kpi:
                continue
            ach, st = evaluate(kpi, e["actual"], th_g, th_y)
            # workflow: past year fully approved; 1405 mixed states for demo realism
            if e["year"] < 1405:
                ws = "approved"
            else:
                ws = "approved" if e["month"] <= 2 else ("qc_reviewed" if e["month"] == 3 else "submitted")
            db.add(models.KPIEntry(
                kpi_id=kpi.id, year=e["year"], month=e["month"], actual=e["actual"],
                achievement=ach, status=st, workflow_state=ws,
                submitted_by=kpi.data_owner_id, approved_by=qm.id if ws == "approved" else None,
            ))

        # seed audit log
        db.add(models.AuditLog(user_id=admin.id, username="admin", entity_type="system",
                               action="seed", new_value=f"{len(kpis)} شاخص و {len(entries)} رکورد بارگذاری شد"))
        db.commit()
        return {"kpis": len(kpis), "entries": len(entries),
                "processes": len(proc_by_code), "divisions": len(div_by_code)}
    finally:
        db.close()


if __name__ == "__main__":
    print(run_seed())
