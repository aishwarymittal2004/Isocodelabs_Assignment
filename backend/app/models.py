from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, LargeBinary, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base, now

class SalesUser(Base):
    __tablename__='sales_users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120))

class SalesInvitation(Base):
    """Single-use invitation; the raw token is only shown to the sales head once."""
    __tablename__ = 'sales_invitations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey('sales_users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Project(Base):
    __tablename__='projects'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    price_min_inr: Mapped[int] = mapped_column(Integer)
    price_max_inr: Mapped[int] = mapped_column(Integer)
    rera_registration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    facts_approved: Mapped[bool] = mapped_column(Boolean, default=False)

class Lead(Base):
    __tablename__='leads'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'))
    source: Mapped[str] = mapped_column(String(40))
    preferred_configuration: Mapped[str | None] = mapped_column(String(20))
    budget_max_inr: Mapped[int | None] = mapped_column(Integer)
    contact_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default='new')
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey('sales_users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Slot(Base):
    __tablename__='slots'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__=(UniqueConstraint('project_id','starts_at', name='uq_project_slot_start'),)

class Booking(Base):
    __tablename__='bookings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id'))
    slot_id: Mapped[str] = mapped_column(ForeignKey('slots.id'))
    status: Mapped[str] = mapped_column(String(20), default='confirmed')
    idempotency_key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__=(
        UniqueConstraint('lead_id','idempotency_key', name='uq_lead_idempotency'),
        Index('uq_active_booking_per_slot','slot_id',unique=True,postgresql_where=text("status = 'confirmed'"),sqlite_where=text("status = 'confirmed'")),
    )

class Message(Base):
    __tablename__='messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id'))
    speaker: Mapped[str] = mapped_column(String(10))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditEvent(Base):
    __tablename__='audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    event: Mapped[str] = mapped_column(String(60))
    subject_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Concern(Base):
    __tablename__ = 'concerns'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id'), index=True)
    source_message_id: Mapped[str] = mapped_column(ForeignKey('messages.id'))
    category: Mapped[str] = mapped_column(String(32))
    evidence_kind: Mapped[str] = mapped_column(String(20))
    evidence_quote: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectFactRevision(Base):
    """Immutable revision history: only status=approved is available to buyers and AI."""
    __tablename__ = 'project_fact_revisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    fact_key: Mapped[str] = mapped_column(String(100), index=True)
    fact_value: Mapped[str] = mapped_column(String(700))
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('sales_users.id'))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('sales_users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class ReminderOutbox(Base):
    """Mocked notification intents, not actual SMS / WhatsApp messages."""
    __tablename__ = 'reminder_outbox'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey('bookings.id'), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__=(UniqueConstraint('booking_id','kind',name='uq_booking_reminder_kind'),)


class BuyerCredential(Base):
    """Password-based demo sign-in scoped to a buyer's project enquiry.

    This is independent of the short-lived buyer JWT. A phone number alone
    can never grant access to an existing booking.
    """
    __tablename__ = 'buyer_credentials'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id'), unique=True, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'))
    phone: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('project_id', 'phone', name='uq_buyer_login_per_project'),)


class ProjectSalesperson(Base):
    """Public contact card for a project, separate from the staff login account.

    Edits return the card to review; only a sales head may approve public exposure.
    """
    __tablename__ = 'project_salespeople'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role_title: Mapped[str] = mapped_column(String(100), default='Sales executive')
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AIReviewFlag(Base):
    """A per-message, auditable human review item. Created even for model failure."""
    __tablename__ = 'ai_review_flags'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id'), index=True)
    source_message_id: Mapped[str] = mapped_column(ForeignKey('messages.id'), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('sales_users.id'), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ProjectImage(Base):
    """Sanitized project photo stored in the DB for persistence across restarts.

    Buyers only get sales-head-approved images of published projects.
    """
    __tablename__ = 'project_images'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary)
    mime_type: Mapped[str] = mapped_column(String(32), default='image/jpeg')
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
