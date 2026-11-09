# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import (String, Integer, Float, Boolean, DateTime, ForeignKey,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)   # admin, process_owner, quality, executive
    name_fa: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), default="")
    hashed_password: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    process_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # per-user view permissions (JSON list); NULL -> role default (ROLE_PERMS)
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # force the user to change the password on next login
    must_change: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    role: Mapped["Role"] = relationship()
    process: Mapped["OrgUnit"] = relationship(foreign_keys=[process_id])


class OrgUnit(Base):
    """Self-referential org tree: company -> division -> process (leaf)."""
    __tablename__ = "org_units"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(20))  # company | division | process
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped["OrgUnit"] = relationship(remote_side=[id], foreign_keys=[parent_id])
    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])


class KPI(Base):
    __tablename__ = "kpis"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    process_id: Mapped[int] = mapped_column(ForeignKey("org_units.id"))
    uom: Mapped[str] = mapped_column(String(30))            # percent, count, days, ppm...
    direction: Mapped[str] = mapped_column(String(6))        # up | down
    frequency: Mapped[str] = mapped_column(String(16))       # monthly, quarterly, semiannual, annual, event
    target: Mapped[float] = mapped_column(Float)
    warning: Mapped[float] = mapped_column(Float)
    critical: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1)
    importance: Mapped[str] = mapped_column(String(16), default="operational")  # key | operational
    is_strategic: Mapped[bool] = mapped_column(Boolean, default=False)
    definition: Mapped[str] = mapped_column(Text, default="")
    formula: Mapped[str] = mapped_column(Text, default="")
    acceptance_text: Mapped[str] = mapped_column(String(120), default="")
    calc_mode: Mapped[str] = mapped_column(String(16), default="achievement")   # achievement | band
    th_green: Mapped[float | None] = mapped_column(Float, nullable=True)
    th_yellow: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    process: Mapped["OrgUnit"] = relationship()


class KPIEntry(Base):
    __tablename__ = "kpi_entries"
    __table_args__ = (UniqueConstraint("kpi_id", "year", "month", name="uq_entry_period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)     # Jalali year
    month: Mapped[int] = mapped_column(Integer, index=True)    # 1..12
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    achievement: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String(8), nullable=True)  # green|yellow|red
    comment: Mapped[str] = mapped_column(Text, default="")
    deviation_cause: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    workflow_state: Mapped[str] = mapped_column(String(16), default="draft")
    # draft -> submitted -> qc_reviewed -> approved  (or rejected)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kpi: Mapped["KPI"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(60), default="")
    entity_type: Mapped[str] = mapped_column(String(40))      # kpi, entry, user, org, setting
    entity_id: Mapped[str] = mapped_column(String(40), default="")
    action: Mapped[str] = mapped_column(String(30))           # create, update, delete, submit, approve...
    field: Mapped[str] = mapped_column(String(60), default="")
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class LoginLock(Base):
    """Failed-login attempt counters / lock windows (offline parity: 5 tries / 5 min)."""
    __tablename__ = "login_locks"
    username: Mapped[str] = mapped_column(String(60), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StrategyGoal(Base):
    """Strategic goal (offline 'strategy' view): plans independent of operational KPI targets."""
    __tablename__ = "strategy_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("org_units.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_process_code: Mapped[str] = mapped_column(String(30), default="")
    start_period: Mapped[int] = mapped_column(Integer)   # year*12 + (month-1)
    end_period: Mapped[int] = mapped_column(Integer)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StrategyLink(Base):
    """KPI attached to a goal with an evaluation mode and baseline."""
    __tablename__ = "strategy_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("strategy_goals.id"), index=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16), default="improve")  # improve | maintain
    baseline: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON snapshot: {target, weight, note, fingerprint} (offline link fields)
    snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    goal: Mapped["StrategyGoal"] = relationship()
    kpi: Mapped["KPI"] = relationship()


class StrategyAction(Base):
    """Action plan attached to a goal (optionally driven by a KPI link)."""
    __tablename__ = "strategy_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("strategy_goals.id"), index=True)
    link_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_links.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_period: Mapped[int] = mapped_column(Integer)
    rule: Mapped[str] = mapped_column(String(16), default="always")  # always|behind|below|above
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="planned")  # planned|in_progress|blocked|done
    progress: Mapped[float] = mapped_column(Float, default=0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    goal: Mapped["StrategyGoal"] = relationship()
    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])


class StrategyEvent(Base):
    """Audit/history stream of strategy changes (offline strategyEvent)."""
    __tablename__ = "strategy_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("strategy_goals.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="")  # JSON string
