"""Pydantic schemas — Mourad.Soltani."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class LineItemIn(BaseModel):
    description: str
    qty: float = 1.0
    unit_price: float = 0.0


class LineItemOut(LineItemIn):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ClientIn(BaseModel):
    name: str
    email: str = ""
    company: str = ""
    notes: str = ""


class ClientOut(ClientIn):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InvoiceIn(BaseModel):
    client_id: int
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    status: str = "draft"
    currency: str = "USD"
    notes: str = ""
    items: List[LineItemIn] = Field(default_factory=list)


class InvoiceOut(BaseModel):
    id: int
    number: str
    client_id: int
    issue_date: Optional[date]
    due_date: Optional[date]
    status: str
    currency: str
    notes: str
    total: float
    items: List[LineItemOut]
    model_config = ConfigDict(from_attributes=True)


class ExpenseIn(BaseModel):
    client_id: Optional[int] = None
    category: str = "general"
    description: str = ""
    amount: float
    incurred_on: Optional[date] = None
    billable: bool = True


class ExpenseOut(ExpenseIn):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProposalIn(BaseModel):
    title: str
    client_name: str = ""
    problem: str = ""
    solution: str = ""
    scope: str = ""
    investment: float = 0.0
    timeline: str = ""


class ProposalOut(ProposalIn):
    id: int
    body: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class HealthOut(BaseModel):
    status: str
    product: str
    author: str
    version: str
    checks: dict
