"""SQLAlchemy models — Mourad.Soltani / ForgeLedger."""

from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), default="")
    company = Column(String(200), default="")
    notes = Column(Text, default="")
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="client")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    number = Column(String(40), unique=True, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    issue_date = Column(Date, default=date.today)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="draft")  # draft, sent, paid, overdue
    currency = Column(String(8), default="USD")
    notes = Column(Text, default="")
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    client = relationship("Client", back_populates="invoices")
    items = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        return round(sum(i.qty * i.unit_price for i in self.items), 2)


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String(400), nullable=False)
    qty = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)
    invoice = relationship("Invoice", back_populates="items")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    category = Column(String(80), default="general")
    description = Column(String(400), default="")
    amount = Column(Float, nullable=False)
    incurred_on = Column(Date, default=date.today)
    billable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    client = relationship("Client", back_populates="expenses")


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    client_name = Column(String(200), default="")
    problem = Column(Text, default="")
    solution = Column(Text, default="")
    scope = Column(Text, default="")
    investment = Column(Float, default=0.0)
    timeline = Column(String(200), default="")
    body = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class RecurringInvoice(Base):
    __tablename__ = "recurring_invoices"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    cadence = Column(String(20), default="monthly")  # weekly, monthly, quarterly
    next_run = Column(Date, nullable=False)
    currency = Column(String(8), default="USD")
    description = Column(String(400), default="Retainer")
    amount = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    last_invoice_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
