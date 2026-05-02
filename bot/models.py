"""
Pydantic request / response models for all 5 endpoints.
Matches the judge's expected payload shapes exactly.
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── /v1/healthz ───

class ContextsLoaded(BaseModel):
    category: int = 0
    merchant: int = 0
    customer: int = 0
    trigger: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: int = 0
    contexts_loaded: ContextsLoaded = Field(default_factory=ContextsLoaded)


# ─── /v1/metadata ───

class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    version: str


# ─── /v1/context ───

class ContextRequest(BaseModel):
    scope: str                          # "category" | "merchant" | "customer" | "trigger"
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class ContextAccepted(BaseModel):
    accepted: bool = True
    ack_id: str = ""
    stored_at: str = ""


class ContextRejected(BaseModel):
    accepted: bool = False
    reason: str = "stale_version"
    current_version: int = 0


# ─── /v1/tick ───

class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class TickAction(BaseModel):
    conversation_id: str = ""
    merchant_id: str = ""
    customer_id: Optional[str] = None
    send_as: str = "vera"               # "vera" | "merchant_on_behalf"
    trigger_id: str = ""
    template_name: str = ""
    template_params: list[str] = Field(default_factory=list)
    body: str = ""
    cta: str = "open_ended"
    suppression_key: str = ""
    rationale: str = ""


class TickResponse(BaseModel):
    actions: list[TickAction] = Field(default_factory=list)


# ─── /v1/reply ───

class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str = "merchant"         # "merchant" | "customer"
    message: str = ""
    received_at: Optional[str] = None
    turn_number: int = 1


class ReplyResponse(BaseModel):
    action: str = "send"                # "send" | "wait" | "end"
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str = ""
