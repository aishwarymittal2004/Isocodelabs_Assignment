"""Additive ticket tables; no alterations to existing leads, messages or bookings."""
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .core import Base,now

class BuyerTicket(Base):
    __tablename__='buyer_tickets'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    reference:Mapped[str]=mapped_column(String(24),unique=True,index=True)
    lead_id:Mapped[str]=mapped_column(ForeignKey('leads.id'),unique=True,index=True)
    status:Mapped[str]=mapped_column(String(20),default='ai_active',index=True)
    owner_user_id:Mapped[str|None]=mapped_column(ForeignKey('sales_users.id'),nullable=True)
    requirements_json:Mapped[str]=mapped_column(Text,default='{}')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    accepted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class TicketProject(Base):
    __tablename__='ticket_projects'
    ticket_id:Mapped[str]=mapped_column(ForeignKey('buyer_tickets.id'),primary_key=True)
    project_id:Mapped[str]=mapped_column(ForeignKey('projects.id'),primary_key=True)

class TicketEvent(Base):
    __tablename__='ticket_events'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    ticket_id:Mapped[str]=mapped_column(ForeignKey('buyer_tickets.id'),index=True)
    kind:Mapped[str]=mapped_column(String(36))
    actor_type:Mapped[str]=mapped_column(String(12))
    actor_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    detail:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class TicketNotification(Base):
    __tablename__='ticket_notifications'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    ticket_id:Mapped[str]=mapped_column(ForeignKey('buyer_tickets.id'),index=True)
    kind:Mapped[str]=mapped_column(String(30))
    state:Mapped[str]=mapped_column(String(20),default='pending')
    note:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
