# -*- coding: utf-8 -*-
from typing import Optional
from pydantic import BaseModel


class LoginResp(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role_code: str
    role_name: str
    process_id: Optional[int] = None
    process_name: Optional[str] = None
    is_active: bool
    permissions: Optional[list] = None   # explicit per-view override (null = role default)
    must_change: bool = False


class UserIn(BaseModel):
    username: str
    full_name: str
    email: str = ""
    password: Optional[str] = None
    role_code: str
    process_id: Optional[int] = None
    is_active: bool = True
    permissions: Optional[list] = None   # null -> keep role default
    must_change: bool = False


class ChangePasswordIn(BaseModel):
    current_password: str = ""
    new_password: str


class AdminRecoveryIn(BaseModel):
    confirm: str = ""


class CompleteSetupIn(BaseModel):
    token: str
    password: str
    password2: str = ""


class KPIIn(BaseModel):
    code: Optional[str] = None
    name: str
    process_id: int
    uom: str = "percent"
    direction: str = "up"
    frequency: str = "monthly"
    target: float
    warning: float
    critical: float
    weight: float = 1
    importance: str = "operational"
    is_strategic: bool = False
    definition: str = ""
    formula: str = ""
    acceptance_text: str = ""
    calc_mode: str = "achievement"
    th_green: Optional[float] = None
    th_yellow: Optional[float] = None
    data_owner_id: Optional[int] = None
    approver_id: Optional[int] = None
    active: bool = True
    reason: str = ""   # required for change-log on edits


class EntryIn(BaseModel):
    kpi_id: int
    year: int
    month: int
    actual: Optional[float] = None
    comment: str = ""
    deviation_cause: str = ""
    corrective_action: str = ""


class WorkflowAction(BaseModel):
    entry_id: int
    action: str            # submit | review | approve | reject | reopen
    reason: str = ""


class OrgIn(BaseModel):
    code: str
    name: str
    level: str
    parent_id: Optional[int] = None
    owner_user_id: Optional[int] = None
