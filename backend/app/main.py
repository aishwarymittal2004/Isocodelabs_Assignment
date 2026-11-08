import os
import uuid
import secrets
import hashlib
from io import BytesIO
from datetime import datetime, timezone, timedelta
from time import perf_counter
from typing import Annotated
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, Header, HTTPException, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .core import Base, engine, get_db, make_token, now, buyer, sales, password_hasher
from .models import SalesUser, SalesInvitation, Project, Lead, Slot, Booking, Message, AuditEvent, Concern, ProjectFactRevision, ReminderOutbox, BuyerCredential, ProjectSalesperson, ProjectImage, AIReviewFlag
from .agent import decide, safe_response, LocalAgentUnavailable, translated_reply, preferred_language, route_latest_message, fast_route, AgentDecision
from .schemas import LeadCreate, Login, BookRequest, ConsentUpdate, SlotCreate, MessageCreate
from pydantic import BaseModel, Field
from .reminders import schedule_reminders, suppress_pending, run_due
from .conversation import draft_contextual_reply, eligible_for_contextual_reply, bounded_history, MAX_HISTORY_TURNS
from .ticket_flow import ensure_ticket, request_human, accept_ticket, ticket_for_lead, handle_ticket_message, accepted_ticket_locked
from .tickets_router import router as ticket_router
from .ai_policy import (wants_human, looks_like_fact_request, asks_final_price_or_discount,
                        allowed_facts, fact_result, missing_fact_reply, final_price_reply, human_reply)

TICKET_BUILD = 'sitepilot-ticket-ownership-v9'
CHAT_FIX_BUILD = 'sitepilot-reliability-v7.2'
AI_POLICY_REVISION = 'sitepilot-ai-policy-v8-update9'

app = FastAPI(title='SitePilot AI Backend', version='0.1.0', description='SitePilot API: private local-model concern classification, server-controlled facts and bookings.')
app.include_router(ticket_router)
# CORS configuration. For local development, allow frontend dev servers running
# on localhost / 127.0.0.1 at any port (Vite, TanStack Start, etc.).
# In production, set APP_ENV=production and CORS_ORIGINS to the exact HTTPS
# frontend origin(s), separated by commas. Never use '*' for production.
origins = [
    origin.strip().rstrip('/')
    for origin in os.getenv(
        'CORS_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000,'
        'http://localhost:5173,http://127.0.0.1:5173',
    ).split(',')
    if origin.strip()
]
is_development = os.getenv('APP_ENV', 'development').lower() != 'production'

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r'^http://(localhost|127\.0\.0\.1):[0-9]{2,5}$' if is_development else None,
    allow_credentials=False,  # The app uses Authorization bearer tokens, not cookies.
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key', 'Accept'],
    max_age=600,
)

# Database schema creation must be explicit (python -m app.seed for local demos).
# Never issue DDL merely because a web worker imports this module.

def uid(): return str(uuid.uuid4())

def ensure_project(db: Session, id: str):
    p=db.get(Project,id)
    if not p or not p.facts_approved: raise HTTPException(404,'Approved project not found')
    return p

def normalize_phone(phone: str) -> str:
    return phone if phone.startswith('+') else '+91'+phone if len(phone)==10 else '+'+phone

def own_lead(db: Session, id: str):
    lead=db.get(Lead,id)
    if not lead: raise HTTPException(404,'Lead not found')
    return lead

def is_sales_head(user: SalesUser) -> bool:
    head_email=os.getenv('SALES_HEAD_EMAIL','reviewer@example.test').strip().lower()
    return bool(head_email) and user.email.lower()==head_email

def require_sales_head(db: Session, user_id: str):
    user=db.get(SalesUser,user_id)
    if user is None: raise HTTPException(401,'Account unavailable')
    if not is_sales_head(user):raise HTTPException(403,'Sales head approval required')
    return user

def approved_facts(db: Session, project_id: str):
    revisions=db.scalars(select(ProjectFactRevision).where(
        ProjectFactRevision.project_id==project_id,
        ProjectFactRevision.status=='approved').order_by(ProjectFactRevision.created_at,ProjectFactRevision.id)).all()
    latest={}
    for fact in revisions: latest[fact.fact_key]=fact
    return latest

def serialize_fact(f:ProjectFactRevision):
    return {'id':f.id,'project_id':f.project_id,'key':f.fact_key,'value':f.fact_value,
            'status':f.status,'created_at':f.created_at.isoformat(),
            'reviewed_at':f.reviewed_at.isoformat() if f.reviewed_at else None}

def serialize_project(p, db: Session):
    # Public imagery is never drawn from pending or unapproved uploads.
    # Using a separate field preserves clients that already consume project objects.
    photo=None
    if p.facts_approved:
        img=db.scalar(select(ProjectImage.id).where(ProjectImage.project_id==p.id,ProjectImage.approved.is_(True)).order_by(ProjectImage.created_at.desc()))
        if img: photo=f'/api/v1/projects/{p.id}/images/{img}'
    return dict(id=p.id,name=p.name,city=p.city,description=p.description,price_min_inr=p.price_min_inr,price_max_inr=p.price_max_inr,rera_registration=p.rera_registration,cover_image_url=photo)

def serialize_booking(db,b):
    s=db.get(Slot,b.slot_id)
    return dict(booking_id=b.id,status=b.status,project_id=s.project_id,slot_id=b.slot_id,starts_at=s.starts_at.isoformat(),ends_at=s.ends_at.isoformat(),reminder_status='tracked_in_outbox')

@app.get('/health')
def health():
    # Liveness must not require a live database or model (which may be restarting).
    return {'status':'ok','api':'v1','build':CHAT_FIX_BUILD,'ai_policy_revision':AI_POLICY_REVISION}

@app.get('/ready')
def ready(db: Annotated[Session, Depends(get_db)]):
    # Readiness checks the actual DB connection without exposing credentials.
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(status_code=503, detail='Database unavailable')
    return {'status':'ready','database':'connected'}


@app.post('/api/v1/auth/login')
def login(data: Login,db: Annotated[Session,Depends(get_db)]):
    u=db.scalar(select(SalesUser).where(SalesUser.email==data.email.lower().strip()))
    if u is None or not password_hasher.verify(data.password,u.password_hash): raise HTTPException(401,'Invalid credentials')
    return {'access_token':make_token(u.id,'sales'),'token_type':'bearer','expires_in':7200}

# Sales users cannot self-register publicly. The head issues a single-use
# invitation, and the employee chooses their own password when accepting it.
class SalesInviteCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    display_name: str = Field(min_length=2, max_length=120)

class SalesInviteAccept(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    invitation_code: str = Field(min_length=30, max_length=256)
    password: str = Field(min_length=12, max_length=128)

@app.get('/api/v1/sales/team')
def sales_team(user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    require_sales_head(db, user_id)
    users=db.scalars(select(SalesUser).order_by(SalesUser.display_name)).all()
    return [{'id':u.id,'email':u.email,'display_name':u.display_name,
             'role':'sales_head' if is_sales_head(u) else 'sales'} for u in users]

@app.post('/api/v1/sales/invitations', status_code=201)
def invite_sales_user(payload: SalesInviteCreate, user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    require_sales_head(db, user_id)
    email=payload.email.strip().lower()
    if db.scalar(select(SalesUser.id).where(SalesUser.email==email)):
        raise HTTPException(409, 'A sales account with this email already exists')
    # Expire previous unused codes for the same invited email.
    current=now()
    prior=db.scalars(select(SalesInvitation).where(SalesInvitation.email==email, SalesInvitation.consumed_at.is_(None))).all()
    for invitation in prior: invitation.consumed_at=current
    code=secrets.token_urlsafe(32)
    record=SalesInvitation(id=uid(),email=email,display_name=payload.display_name.strip(),
        token_hash=hashlib.sha256(code.encode()).hexdigest(),invited_by=user_id,
        expires_at=current+timedelta(hours=48))
    db.add(record)
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='sales_invited',subject_id=record.id))
    db.commit()
    return {'email':email,'display_name':record.display_name,'invitation_code':code,
            'expires_at':record.expires_at.isoformat(),
            'message':'Copy this invitation code now. It is displayed only once and expires in 48 hours.'}

@app.post('/api/v1/auth/accept-invitation', status_code=201)
def accept_sales_invitation(payload: SalesInviteAccept, db: Annotated[Session, Depends(get_db)]):
    token_hash=hashlib.sha256(payload.invitation_code.strip().encode()).hexdigest()
    record=db.scalar(select(SalesInvitation).where(SalesInvitation.token_hash==token_hash).with_for_update())
    email=payload.email.strip().lower()
    expiration=None if record is None else (record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc))
    if (record is None or record.consumed_at is not None or expiration <= now() or record.email != email):
        raise HTTPException(400, 'Invitation invalid, expired or already used. Ask the sales head for a new code.')
    if db.scalar(select(SalesUser.id).where(SalesUser.email==record.email)):
        raise HTTPException(409, 'Sales account already exists. Sign in instead.')
    employee=SalesUser(id=uid(),email=record.email,display_name=record.display_name,
                       password_hash=password_hasher.hash(payload.password))
    db.add(employee)
    record.consumed_at=now()
    db.add(AuditEvent(id=uid(),actor_id=employee.id,event='sales_invitation_accepted',subject_id=record.id))
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This invitation has already been used')
    return {'status':'account_created', 'email':record.email,
            'message':'Your sales account is ready. Sign in with your email and password.'}

@app.get('/api/v1/auth/me')
def me(user_id: Annotated[str,Depends(sales)],db: Annotated[Session,Depends(get_db)]):
    u=db.get(SalesUser,user_id)
    if not u: raise HTTPException(401,'Account unavailable')
    return {'id':u.id,'email':u.email,'display_name':u.display_name,'role':'sales_head' if is_sales_head(u) else 'sales'}

@app.get('/api/v1/projects')
def projects(db: Annotated[Session,Depends(get_db)]):
    return [serialize_project(p,db) for p in db.scalars(select(Project).where(Project.facts_approved.is_(True))).all()]

@app.get('/api/v1/projects/{project_id}')
def project(project_id:str,db:Annotated[Session,Depends(get_db)]): return serialize_project(ensure_project(db,project_id),db)


class ProjectDraft(BaseModel):
    name: str = Field(min_length=3,max_length=120)
    city: str = Field(min_length=2,max_length=100)
    description: str = Field(min_length=10,max_length=1500)
    salesperson_name: str | None = Field(default=None, min_length=2, max_length=120)
    salesperson_role: str = Field(default='Sales executive', min_length=2, max_length=100)
    salesperson_phone: str | None = Field(default=None, pattern=r'^\+?[0-9]{10,15}$')
    salesperson_email: str | None = Field(default=None, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$', max_length=255)

class Publication(BaseModel):
    publish: bool

@app.get('/api/v1/sales/projects')
def managed_projects(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    return [dict(serialize_project(p,db), published=p.facts_approved) for p in
            db.scalars(select(Project).order_by(Project.name)).all()]

@app.post('/api/v1/sales/projects',status_code=201)
def add_project(payload:ProjectDraft,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    project=Project(id=uid(),name=payload.name.strip(),city=payload.city.strip(),
                    description=payload.description.strip(),price_min_inr=0,price_max_inr=0,
                    rera_registration=None,facts_approved=False)
    db.add(project)
    contact_fields=[payload.salesperson_name,payload.salesperson_phone,payload.salesperson_email]
    if any(contact_fields) and not all(contact_fields):
        raise HTTPException(422,'Provide salesperson name, phone and email together')
    if all(contact_fields):
        db.add(ProjectSalesperson(id=uid(), project_id=project.id,
            name=payload.salesperson_name.strip(), role_title=payload.salesperson_role.strip(),
            phone=payload.salesperson_phone.strip(), email=payload.salesperson_email.lower().strip(),
            approved=False,active=True))
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_draft_created',subject_id=project.id))
    db.commit()
    return dict(serialize_project(project,db),published=False)

@app.patch('/api/v1/sales/projects/{project_id}/publication')
def publish_project(project_id:str,payload:Publication,user_id:Annotated[str,Depends(sales)],
                    db:Annotated[Session,Depends(get_db)]):
    require_sales_head(db,user_id)
    project=db.get(Project,project_id)
    if not project:raise HTTPException(404,'Project not found')
    if payload.publish:
        approved=approved_facts(db,project_id)
        rera=approved.get('rera_registration')
        if not rera or not rera.fact_value.strip() or len(approved)<2:
            raise HTTPException(409,'Approve RERA registration and at least one other fact before publication')
        project.rera_registration=rera.fact_value.strip()
    project.facts_approved=payload.publish
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_published' if payload.publish else 'project_unpublished',subject_id=project_id))
    db.commit()
    return dict(serialize_project(project,db),published=project.facts_approved)


# Project photos are re-encoded as JPEG to strip metadata, reject scripts and
# avoid serving arbitrary uploads. 3 MiB input, 8-megapixel decoded limit.
MAX_IMAGE_BYTES=3*1024*1024
MAX_IMAGE_PIXELS=8_000_000

def _contact_public(c: ProjectSalesperson):
    return dict(id=c.id,name=c.name,role_title=c.role_title,phone=c.phone,email=c.email)

def _contact_admin(c: ProjectSalesperson):
    return dict(_contact_public(c),approved=c.approved,active=c.active,updated_at=c.updated_at.isoformat())

def _public_salespeople(db: Session, project_id: str):
    return [_contact_public(c) for c in db.scalars(select(ProjectSalesperson).where(
        ProjectSalesperson.project_id==project_id,ProjectSalesperson.approved.is_(True),
        ProjectSalesperson.active.is_(True)).order_by(ProjectSalesperson.updated_at.desc())).all()]

class SalespersonInput(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    role_title: str = Field(default='Sales executive', min_length=2,max_length=100)
    phone: str = Field(pattern=r'^\+?[0-9]{10,15}$')
    email: str = Field(pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$',max_length=255)
    active: bool = True

class ApprovalInput(BaseModel):
    approved: bool

@app.get('/api/v1/projects/{project_id}/salespeople')
def public_salespeople(project_id:str,db:Annotated[Session,Depends(get_db)]):
    ensure_project(db,project_id)
    return _public_salespeople(db,project_id)

@app.get('/api/v1/sales/projects/{project_id}/salespeople')
def admin_salespeople(project_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    if not db.get(Project,project_id):raise HTTPException(404,'Project not found')
    return [_contact_admin(c) for c in db.scalars(select(ProjectSalesperson).where(
        ProjectSalesperson.project_id==project_id).order_by(ProjectSalesperson.updated_at.desc())).all()]

@app.post('/api/v1/sales/projects/{project_id}/salespeople',status_code=201)
def add_salesperson(project_id:str,payload:SalespersonInput,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    if not db.get(Project,project_id):raise HTTPException(404,'Project not found')
    contact=ProjectSalesperson(id=uid(),project_id=project_id,name=payload.name.strip(),
        role_title=payload.role_title.strip(),phone=payload.phone.strip(),email=payload.email.lower().strip(),
        active=payload.active,approved=False,updated_at=now())
    db.add(contact)
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_salesperson_created',subject_id=contact.id))
    db.commit()
    return _contact_admin(contact)

@app.patch('/api/v1/sales/projects/{project_id}/salespeople/{contact_id}')
def edit_salesperson(project_id:str,contact_id:str,payload:SalespersonInput,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    contact=db.get(ProjectSalesperson,contact_id)
    if not contact or contact.project_id!=project_id:raise HTTPException(404,'Salesperson not found')
    contact.name=payload.name.strip();contact.role_title=payload.role_title.strip()
    contact.phone=payload.phone.strip();contact.email=payload.email.lower().strip()
    contact.active=payload.active;contact.approved=False;contact.updated_at=now()
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_salesperson_changed',subject_id=contact.id))
    db.commit()
    return _contact_admin(contact)

@app.patch('/api/v1/sales/projects/{project_id}/salespeople/{contact_id}/approval')
def approve_salesperson(project_id:str,contact_id:str,payload:ApprovalInput,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    require_sales_head(db,user_id)
    contact=db.get(ProjectSalesperson,contact_id)
    if not contact or contact.project_id!=project_id:raise HTTPException(404,'Salesperson not found')
    contact.approved=payload.approved;contact.updated_at=now()
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_salesperson_reviewed',subject_id=contact.id))
    db.commit()
    return _contact_admin(contact)

@app.get('/api/v1/contact')
def public_site_contact(db:Annotated[Session,Depends(get_db)]):
    # Use only details the operator explicitly configured or approved for public display.
    email=os.getenv('SITEPILOT_PUBLIC_CONTACT_EMAIL','').strip()
    phone=os.getenv('SITEPILOT_PUBLIC_CONTACT_PHONE','').strip()
    if not (email or phone):
        contact=db.scalar(select(ProjectSalesperson).join(Project,Project.id==ProjectSalesperson.project_id).where(
            Project.facts_approved.is_(True),ProjectSalesperson.approved.is_(True),
            ProjectSalesperson.active.is_(True)).order_by(ProjectSalesperson.updated_at.desc()))
        if contact:email=contact.email;phone=contact.phone
    return {'email':email or None,'phone':phone or None}

@app.get('/api/v1/sales/projects/{project_id}/images')
def admin_images(project_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    if not db.get(Project,project_id):raise HTTPException(404,'Project not found')
    return [dict(id=i.id,approved=i.approved,preview_url=f'/api/v1/sales/projects/{project_id}/images/{i.id}/file')
            for i in db.scalars(select(ProjectImage).where(ProjectImage.project_id==project_id).order_by(ProjectImage.created_at.desc())).all()]

@app.post('/api/v1/sales/projects/{project_id}/images',status_code=201)
async def upload_project_image(project_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)],file:UploadFile=File(...)):
    if not db.get(Project,project_id):raise HTTPException(404,'Project not found')
    if file.content_type not in ('image/jpeg','image/png','image/webp'):
        raise HTTPException(415,'Use a JPEG, PNG or WebP image')
    body=await file.read(MAX_IMAGE_BYTES+1)
    await file.close()
    if len(body)>MAX_IMAGE_BYTES:raise HTTPException(413,'Maximum image size is 3 MB')
    if not body:raise HTTPException(422,'Empty image')
    try:
        with Image.open(BytesIO(body)) as source:
            if source.width*source.height>MAX_IMAGE_PIXELS or min(source.size)<100:
                raise HTTPException(422,'Images must be at least 100 pixels wide and tall and at most 8 megapixels')
            source.load()
            picture=ImageOps.exif_transpose(source).convert('RGB')
            picture.thumbnail((2600,2600))
            output=BytesIO()
            picture.save(output,format='JPEG',quality=85,optimize=True)
            image_bytes=output.getvalue()
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'Invalid or damaged image')
    count=db.scalar(select(func.count(ProjectImage.id)).where(ProjectImage.project_id==project_id))
    if count>=8:raise HTTPException(409,'Maximum eight images per project')
    photo=ProjectImage(id=uid(),project_id=project_id,image_data=image_bytes,mime_type='image/jpeg',approved=False)
    db.add(photo)
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_image_uploaded',subject_id=photo.id))
    db.commit()
    return dict(id=photo.id,approved=False,preview_url=f'/api/v1/sales/projects/{project_id}/images/{photo.id}/file')

@app.put('/api/v1/sales/projects/{project_id}/images/{image_id}')
async def replace_project_image(
    project_id: str,
    image_id: str,
    user_id: Annotated[str, Depends(sales)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Replace an image without bypassing sales-head approval."""
    require_sales_head(db, user_id)
    photo = db.get(ProjectImage, image_id)
    if photo is None or photo.project_id != project_id:
        raise HTTPException(404, 'Photo not found')

    if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(415, 'Use a JPEG, PNG or WebP image')
    body = await file.read(MAX_IMAGE_BYTES + 1)
    await file.close()
    if len(body) > MAX_IMAGE_BYTES:
        raise HTTPException(413, 'Maximum image size is 3 MB')
    if not body:
        raise HTTPException(422, 'Empty image')

    try:
        with Image.open(BytesIO(body)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS or min(source.size) < 100:
                raise HTTPException(422, 'Images must be at least 100 pixels wide and tall and at most 8 megapixels')
            source.load()
            picture = ImageOps.exif_transpose(source).convert('RGB')
            picture.thumbnail((2600, 2600))
            output = BytesIO()
            picture.save(output, format='JPEG', quality=85, optimize=True)
            image_bytes = output.getvalue()
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, 'Invalid or damaged image')

    photo.image_data = image_bytes
    photo.mime_type = 'image/jpeg'
    photo.approved = False
    db.add(AuditEvent(id=uid(), actor_id=user_id, event='project_image_replaced', subject_id=photo.id))
    db.commit()
    return {'id': photo.id, 'approved': False,
            'preview_url': f'/api/v1/sales/projects/{project_id}/images/{photo.id}/file'}


@app.delete('/api/v1/sales/projects/{project_id}/images/{image_id}')
def delete_project_image(
    project_id: str,
    image_id: str,
    user_id: Annotated[str, Depends(sales)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a project photo and record the action for audit."""
    require_sales_head(db, user_id)
    photo = db.get(ProjectImage, image_id)
    if photo is None or photo.project_id != project_id:
        raise HTTPException(404, 'Photo not found')
    db.add(AuditEvent(id=uid(), actor_id=user_id, event='project_image_deleted', subject_id=photo.id))
    db.delete(photo)
    db.commit()
    return {'deleted': True, 'id': image_id}


@app.patch('/api/v1/sales/projects/{project_id}/images/{image_id}/approval')
def approve_project_image(project_id:str,image_id:str,payload:ApprovalInput,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    require_sales_head(db,user_id)
    photo=db.get(ProjectImage,image_id)
    if not photo or photo.project_id!=project_id:raise HTTPException(404,'Photo not found')
    photo.approved=payload.approved
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='project_image_reviewed',subject_id=photo.id))
    db.commit()
    return {'id':photo.id,'approved':photo.approved}

def _image_response(photo:ProjectImage):
    return Response(photo.image_data,media_type='image/jpeg',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

@app.get('/api/v1/sales/projects/{project_id}/images/{image_id}/file')
def admin_image_file(project_id:str,image_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    photo=db.get(ProjectImage,image_id)
    if not photo or photo.project_id!=project_id:raise HTTPException(404,'Photo not found')
    return _image_response(photo)

@app.get('/api/v1/projects/{project_id}/images/{image_id}')
def public_project_image(project_id:str,image_id:str,db:Annotated[Session,Depends(get_db)]):
    ensure_project(db,project_id)
    photo=db.get(ProjectImage,image_id)
    if not photo or photo.project_id!=project_id or not photo.approved:raise HTTPException(404,'Photo not published')
    return _image_response(photo)

@app.post('/api/v1/leads',status_code=201)
def create_lead(data:LeadCreate, db: Annotated[Session,Depends(get_db)]):
    ensure_project(db,data.project_id)
    # Never reveal duplicate information to unauthenticated visitors.
    normalized=normalize_phone(data.phone)
    lead=Lead(id=uid(),name=data.name.strip(),phone=normalized,project_id=data.project_id,source=data.source,preferred_configuration=data.preferred_configuration,budget_max_inr=data.budget_max_inr,contact_consent=data.contact_consent)
    db.add(lead);db.flush();ensure_ticket(db,lead);db.commit()
    return {'lead_id':lead.id,'status':'new','buyer_session_token':make_token(lead.id,'buyer',minutes=24*60),'token_type':'bearer','next_action':'start_conversation'}


# Optional password sign-in for repeat booking management. Passwords are never
# stored in plaintext and an existing unauthenticated phone cannot claim a lead.
class BuyerRegister(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r'^\+?[0-9]{10,15}$')
    password: str = Field(min_length=10, max_length=128)
    project_id: str
    contact_consent: bool = False

class BuyerSignIn(BaseModel):
    phone: str = Field(pattern=r'^\+?[0-9]{10,15}$')
    password: str
    project_id: str

class BuyerClaim(BaseModel):
    password: str = Field(min_length=10, max_length=128)

@app.post('/api/v1/buyer/auth/register', status_code=201)
def register_buyer(payload: BuyerRegister, db: Annotated[Session, Depends(get_db)]):
    ensure_project(db, payload.project_id)
    phone = normalize_phone(payload.phone)
    existing = db.scalar(select(BuyerCredential).where(
        BuyerCredential.project_id == payload.project_id, BuyerCredential.phone == phone))
    if existing:
        raise HTTPException(409, 'An account exists for this project and phone. Please sign in.')
    lead = Lead(id=uid(), name=payload.name.strip(), phone=phone, project_id=payload.project_id,
                source='website', contact_consent=payload.contact_consent)
    credential = BuyerCredential(id=uid(), lead_id=lead.id, project_id=payload.project_id,
                                  phone=phone, password_hash=password_hasher.hash(payload.password))
    # Flush the parent Lead first so its FK target exists before credential INSERT.
    try:
        db.add(lead)
        db.flush()
        db.add(credential)
        db.add(AuditEvent(id=uid(), actor_id=lead.id, event='buyer_registered', subject_id=lead.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        original = getattr(exc, 'orig', None)
        diagnostic = getattr(original, 'diag', None)
        constraint_name = getattr(diagnostic, 'constraint_name', None)
        sqlstate = getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None)
        # Print only the constraint identifier and SQLSTATE, never phone/password/hash.
        print('BUYER REGISTRATION INTEGRITY ERROR:',
              'constraint=', constraint_name, 'sqlstate=', sqlstate, flush=True)
        # PostgreSQL unique violation. Only the credential's actual unique
        # constraint should be represented as an existing account.
        if sqlstate == '23505' and constraint_name in (
            'uq_buyer_login_per_project', 'buyer_credentials_project_id_phone_key',
        ):
            raise HTTPException(409, 'An account exists for this project and phone. Please sign in.')
        raise HTTPException(500, 'Buyer registration failed because of a database constraint. Check server logs.')
    return {'lead_id': lead.id, 'buyer_session_token': make_token(lead.id,'buyer',minutes=24*60),
            'token_type':'bearer'}

@app.post('/api/v1/buyer/auth/login')
def login_buyer(payload: BuyerSignIn, db: Annotated[Session, Depends(get_db)]):
    phone = normalize_phone(payload.phone)
    credential = db.scalar(select(BuyerCredential).where(
        BuyerCredential.project_id == payload.project_id, BuyerCredential.phone == phone))
    if not credential or not password_hasher.verify(payload.password,credential.password_hash):
        raise HTTPException(401, 'Incorrect phone number, password, or project')
    return {'lead_id':credential.lead_id,
            'buyer_session_token':make_token(credential.lead_id,'buyer',minutes=24*60),
            'token_type':'bearer'}

@app.post('/api/v1/buyer/auth/claim',status_code=201)
def claim_existing_session(payload: BuyerClaim, lead_id: Annotated[str,Depends(buyer)],
                           db: Annotated[Session,Depends(get_db)]):
    lead=own_lead(db,lead_id)
    existing = db.scalar(select(BuyerCredential).where(BuyerCredential.project_id==lead.project_id,
                                                        BuyerCredential.phone==lead.phone))
    if existing:
        raise HTTPException(409,'An account exists for this phone and project. Please sign in.')
    credential=BuyerCredential(id=uid(),lead_id=lead.id,project_id=lead.project_id,
                                phone=lead.phone,password_hash=password_hasher.hash(payload.password))
    db.add(credential)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'An account exists. Please sign in.')
    return {'status':'secured','lead_id':lead.id}

@app.get('/api/v1/buyer/me')
def buyer_me(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    l=own_lead(db,lead_id)
    registered=db.scalar(select(BuyerCredential.id).where(BuyerCredential.lead_id==lead_id)) is not None
    return {'lead_id':l.id,'name':l.name,'project_id':l.project_id,'status':l.status,'contact_consent':l.contact_consent,'has_account':registered}

@app.patch('/api/v1/buyer/preferences')
def update_consent(data:ConsentUpdate,lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    l=own_lead(db,lead_id);l.contact_consent=data.contact_consent
    db.add(AuditEvent(id=uid(),actor_id=lead_id,event='contact_consent_changed',subject_id=lead_id));db.commit()
    if not l.contact_consent:
        for booking in db.scalars(select(Booking).where(Booking.lead_id==lead_id)).all():
            suppress_pending(db,booking.id)
        db.commit()
    return {'contact_consent':l.contact_consent}

class ReviewResolution(BaseModel):
    note: str = Field(min_length=3,max_length=500)


@app.get('/api/v1/sales/ai-review')
def ai_review_queue(user_id:Annotated[str,Depends(sales)], db:Annotated[Session,Depends(get_db)],
                    status:str=Query('open',pattern='^(open|reviewed|all)$')):
    """Human-operated daily review queue, latest first; sales-head permission only."""
    require_sales_head(db,user_id)
    query=select(AIReviewFlag).order_by(AIReviewFlag.created_at.desc(), AIReviewFlag.id.desc()).limit(250)
    if status!='all':query=query.where(AIReviewFlag.status==status)
    flags=db.scalars(query).all()
    rows=[]
    for flag in flags:
        lead=db.get(Lead,flag.lead_id)
        msg=db.get(Message,flag.source_message_id)
        rows.append({'id':flag.id,'lead_id':flag.lead_id,
                     'project_id':lead.project_id if lead else None,
                     'buyer_name':lead.name if lead else '(unknown)',
                     'contact_consent':bool(lead and lead.contact_consent),
                     'source_message':msg.body[:300] if msg else '',
                     'reason':flag.reason,'status':flag.status,
                     'created_at':flag.created_at.isoformat(),
                     'reviewed_at':flag.reviewed_at.isoformat() if flag.reviewed_at else None,
                     'review_note':flag.review_note})
    return {'items':rows,'timezone':'Asia/Kolkata',
            'review_policy':'Sales head checks open flags daily; no automatic human review is claimed.'}


@app.post('/api/v1/sales/ai-review/{flag_id}/review')
def mark_ai_flag_reviewed(flag_id:str,payload:ReviewResolution,
                          user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    require_sales_head(db,user_id)
    flag=db.scalar(select(AIReviewFlag).where(AIReviewFlag.id==flag_id).with_for_update())
    if flag is None:raise HTTPException(404,'Flag not found')
    if flag.status!='open':raise HTTPException(409,'Flag already reviewed')
    flag.status='reviewed'
    flag.reviewed_by=user_id
    flag.reviewed_at=now()
    flag.review_note=payload.note.strip()
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='ai_flag_reviewed',subject_id=flag.id))
    db.commit()
    return {'id':flag.id,'status':flag.status,'reviewed_at':flag.reviewed_at.isoformat()}


@app.get('/api/v1/sales/leads')
def sales_leads(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)],status:str|None=None):
    stmt=select(Lead).order_by(Lead.created_at.desc()).limit(100)
    if status: stmt=stmt.where(Lead.status==status)
    return [{'lead_id':l.id,'name':l.name,'phone':l.phone[-4:].rjust(len(l.phone),'*'),'source':l.source,'project_id':l.project_id,'status':l.status,'contact_consent':l.contact_consent,'preferred_configuration':l.preferred_configuration,'budget_max_inr':l.budget_max_inr,'assigned_user_id':l.assigned_user_id,'created_at':l.created_at.isoformat()} for l in db.scalars(stmt).all()]

@app.get('/api/v1/sales/leads/duplicates')
def duplicate_leads(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    counts=select(Lead.phone).group_by(Lead.phone).having(func.count(Lead.id)>1).subquery()
    matches=db.scalars(select(Lead).where(Lead.phone.in_(select(counts.c.phone))).order_by(Lead.phone,Lead.created_at)).all()
    grouped={}
    for l in matches:
        grouped.setdefault(l.phone[-4:].rjust(len(l.phone),'*'),[]).append({'lead_id':l.id,'project_id':l.project_id,'created_at':l.created_at.isoformat()})
    return [{'masked_phone':k,'candidates':v} for k,v in grouped.items()]

def record_handoff(db: Session, lead: Lead, reason: str = 'buyer_request') -> bool:
    """Save a real handoff in the existing lead workflow; caller commits."""
    created=lead.status!='handoff_requested'
    if created:
        lead.status='handoff_requested'
        db.add(AuditEvent(id=uid(),actor_id=lead.id,event='handoff_requested',subject_id=lead.id))
    return created


def flag_ai_review(db: Session, lead_id: str, message_id: str, reason: str):
    """One durable flag per buyer message, never one per model retry."""
    flag=AIReviewFlag(id=uid(), lead_id=lead_id, source_message_id=message_id, reason=reason, status='open')
    db.add(flag)
    return flag


@app.post('/api/v1/buyer/handoff',status_code=202)
def request_handoff(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    l=own_lead(db,lead_id)
    old_ticket=ticket_for_lead(db,l.id)
    already_pending=bool(old_ticket and old_ticket.status=='pending')
    t=request_human(db,l)
    # Preserve the existing V8 sales-head AI review queue when present.
    # Flush the parent message first to satisfy PostgreSQL FK constraints.
    review_fn=globals().get('flag_ai_review')
    if t.status=='pending' and not already_pending and callable(review_fn):
        action=Message(id=uid(),lead_id=l.id,speaker='buyer',body='Requested a salesperson via the handoff button.')
        db.add(action);db.flush()
        review_fn(db,l.id,action.id,'human_requested')
    db.commit()
    return {'lead_id':l.id,'status':'handoff_requested' if t.status=='pending' else t.status,
            'assignment_status':'pending' if t.status=='pending' else 'assigned',
            'message':'Your request is recorded in the sales team queue under ticket '+t.reference+'. The AI can still assist while waiting for a salesperson to accept.' if t.status=='pending' else 'A salesperson has accepted this ticket.',
            'ticket_reference':t.reference,'salespeople':_public_salespeople(db,l.project_id) if db.get(Project,l.project_id).facts_approved else []}

@app.get('/api/v1/buyer/handoff')
def my_handoff_status(lead_id: Annotated[str,Depends(buyer)],db: Annotated[Session,Depends(get_db)]):
    l=own_lead(db,lead_id);t=ensure_ticket(db,l);db.commit()
    return {'status':'handoff_requested' if t.status=='pending' else t.status,
            'assigned':t.status in ('accepted','resolved'),'ticket_reference':t.reference,
            'message':('A salesperson has accepted this ticket; AI responses are now disabled.' if t.status in ('accepted','resolved') else 'Request pending; AI continues answering approved facts.' if t.status=='pending' else 'AI assistance active.'),
            'salespeople':_public_salespeople(db,l.project_id) if db.get(Project,l.project_id).facts_approved else []}

@app.post('/api/v1/sales/leads/{lead_id}/handoff/accept')
def accept_handoff(lead_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    l=own_lead(db,lead_id)
    t=accept_ticket(db,l,user_id)
    db.commit()
    return {'status':'human_accepted','assigned':True,'ticket_reference':t.reference,'owner_user_id':user_id}

@app.get('/api/v1/sales/handoffs')
def handoffs(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    leads=db.scalars(select(Lead).where(Lead.status=='handoff_requested',Lead.assigned_user_id.is_(None)).order_by(Lead.created_at).limit(100)).all()
    return [{'lead_id':l.id,'name':l.name,'project_id':l.project_id,'status':l.status,'contact_consent':l.contact_consent} for l in leads]

@app.get('/api/v1/sales/leads/{lead_id}')
def sales_lead(lead_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    l=own_lead(db,lead_id)
    return {'lead_id':l.id,'name':l.name,'phone':l.phone[-4:].rjust(len(l.phone),'*'),'source':l.source,'project_id':l.project_id,'status':l.status,'contact_consent':l.contact_consent,'preferred_configuration':l.preferred_configuration,'budget_max_inr':l.budget_max_inr,'assigned_user_id':l.assigned_user_id,'created_at':l.created_at.isoformat()}

@app.get('/api/v1/projects/{project_id}/slots')
def available_slots(project_id:str,db:Annotated[Session,Depends(get_db)],date:str=Query(...,description='YYYY-MM-DD')):
    # Public approved visit-slot availability contains no buyer information.
    # Booking remains restricted to the authenticated buyer for this project.
    ensure_project(db,project_id)
    try: target=datetime.strptime(date,'%Y-%m-%d').date()
    except ValueError: raise HTTPException(422,'Date must use YYYY-MM-DD')
    rows=db.scalars(select(Slot).where(Slot.project_id==project_id,Slot.enabled.is_(True)).order_by(Slot.starts_at)).all()
    occupied=set(db.scalars(select(Booking.slot_id).where(Booking.status=='confirmed')).all())
    matches=[]
    for s in rows:
        dt=s.starts_at if s.starts_at.tzinfo else s.starts_at.replace(tzinfo=timezone.utc)
        if dt.astimezone(ZoneInfo('Asia/Kolkata')).date()==target and dt>now():
            matches.append({'slot_id':s.id,'starts_at':dt.isoformat(),'ends_at':s.ends_at.isoformat(),'available':s.id not in occupied})
    return {'project_id':project_id,'date':date,'timezone':'Asia/Kolkata','slots':matches}

@app.post('/api/v1/buyer/bookings',status_code=201)
def book(data:BookRequest,lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)],idempotency_key:Annotated[str,Header(alias='Idempotency-Key',min_length=8,max_length=100)]):
    l=own_lead(db,lead_id)
    if l.project_id!=data.project_id: raise HTTPException(403,'Project not associated with enquiry')
    prior=db.scalar(select(Booking).where(Booking.lead_id==lead_id,Booking.idempotency_key==idempotency_key))
    if prior:
        if prior.slot_id!=data.slot_id:raise HTTPException(409,'Idempotency key already used for a different slot')
        return serialize_booking(db,prior)
    # Row lock serializes availability changes on PostgreSQL.
    slot=db.scalar(select(Slot).where(Slot.id==data.slot_id).with_for_update())
    if not slot or slot.project_id!=data.project_id or not slot.enabled: raise HTTPException(404,'Slot unavailable')
    start=slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=timezone.utc)
    if start<=now(): raise HTTPException(409,'Cannot book a past slot')
    db.add(Booking(id=uid(),lead_id=lead_id,slot_id=slot.id,status='confirmed',idempotency_key=idempotency_key))
    db.add(AuditEvent(id=uid(),actor_id=lead_id,event='booking_confirmed',subject_id=slot.id))
    try:
        db.flush()
        created=db.scalar(select(Booking).where(Booking.lead_id==lead_id,Booking.idempotency_key==idempotency_key))
        schedule_reminders(db,created,slot,l)
        db.commit()
    except IntegrityError:
        db.rollback()
        prior=db.scalar(select(Booking).where(Booking.lead_id==lead_id,Booking.idempotency_key==idempotency_key))
        if prior:
            if prior.slot_id!=data.slot_id: raise HTTPException(409,'Idempotency key already used for a different slot')
            return serialize_booking(db,prior)
        raise HTTPException(409,detail='SLOT_UNAVAILABLE')
    b=db.scalar(select(Booking).where(Booking.lead_id==lead_id,Booking.idempotency_key==idempotency_key))
    return serialize_booking(db,b)

@app.get('/api/v1/buyer/bookings')
def my_bookings(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    return [serialize_booking(db,b) for b in db.scalars(select(Booking).where(Booking.lead_id==lead_id).order_by(Booking.created_at.desc())).all()]

@app.post('/api/v1/buyer/bookings/{booking_id}/cancel')
def cancel(booking_id:str,lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    b=db.scalar(select(Booking).where(Booking.id==booking_id,Booking.lead_id==lead_id).with_for_update())
    if not b: raise HTTPException(404,'Booking not found')
    if b.status=='cancelled': return serialize_booking(db,b)
    if b.status!='confirmed':raise HTTPException(409,'Booking cannot be cancelled')
    b.status='cancelled';suppress_pending(db,b.id);db.add(AuditEvent(id=uid(),actor_id=lead_id,event='booking_cancelled',subject_id=b.id));db.commit()
    return serialize_booking(db,b)

@app.get('/api/v1/sales/bookings')
def sales_bookings(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    return [serialize_booking(db,b) | {'lead_id':b.lead_id,'lead_name':db.get(Lead,b.lead_id).name} for b in db.scalars(select(Booking).order_by(Booking.created_at.desc()).limit(100)).all()]

@app.post('/api/v1/sales/slots',status_code=201)
def create_slot(data:SlotCreate,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    ensure_project(db,data.project_id)
    if data.starts_at<=now() or data.ends_at<=data.starts_at: raise HTTPException(422,'Future start and later end required')
    s=Slot(id=uid(),project_id=data.project_id,starts_at=data.starts_at,ends_at=data.ends_at,enabled=True)
    db.add(s)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'A slot already starts at this time')
    return {'slot_id':s.id,'project_id':s.project_id,'starts_at':s.starts_at.isoformat(),'ends_at':s.ends_at.isoformat()}

@app.get('/api/v1/buyer/conversations/messages')
def read_messages(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    own_lead(db,lead_id)
    return [{'message_id':m.id,'speaker':m.speaker,'message':m.body,'created_at':m.created_at.isoformat()} for m in db.scalars(select(Message).where(Message.lead_id==lead_id).order_by(Message.created_at)).all()]


# Milestone 4: narrow, read-only booking tool invoked by the AI booking intent.
# Selection and commit are deliberately separate; the buyer must confirm.
def _next_available_slots(db: Session, project_id: str, limit: int = 5):
    ensure_project(db, project_id)
    slots = db.scalars(select(Slot).where(
        Slot.project_id == project_id,
        Slot.enabled.is_(True),
        Slot.starts_at > now(),
    ).order_by(Slot.starts_at).limit(200)).all()
    booked = set(db.scalars(select(Booking.slot_id).where(
        Booking.status == 'confirmed',
        Booking.slot_id.in_([slot.id for slot in slots]),
    )).all()) if slots else set()
    return [dict(slot_id=s.id, project_id=s.project_id,
                 starts_at=s.starts_at.isoformat(), ends_at=s.ends_at.isoformat(),
                 timezone='Asia/Kolkata') for s in slots if s.id not in booked][:limit]

@app.get('/api/v1/buyer/assistant/booking-options')
def assistant_booking_options(lead_id: Annotated[str, Depends(buyer)],
                              db: Annotated[Session, Depends(get_db)]):
    lead = own_lead(db, lead_id)
    return {'project_id': lead.project_id, 'confirmation_required': True,
            'slots': _next_available_slots(db, lead.project_id)}

@app.post('/api/v1/buyer/conversations/messages')
def chat_message(data:MessageCreate,lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    """Fail-closed tool controller: messages, factual responses, and escalations are durable.

    Model-generated text is used only for carefully validated non-factual dialogue.
    The model never writes a booking, claims a discount, or sets a fact's approval.
    """
    _ticket_lead = own_lead(db, lead_id)
    ticket_override = handle_ticket_message(db, _ticket_lead, data.message)
    if ticket_override is not None:
        return ticket_override
    lead=own_lead(db,lead_id)
    project=ensure_project(db,lead.project_id)
    previous=db.scalars(select(Message).where(Message.lead_id==lead_id)
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(MAX_HISTORY_TURNS)).all()
    history=bounded_history([{'speaker':row.speaker,'body':row.body} for row in reversed(previous)])
    message=Message(id=uid(),lead_id=lead_id,speaker='buyer',body=data.message)
    db.add(message)
    db.commit()  # Preserve the buyer message, even if the model fails.
    language=preferred_language(data.message,data.language)
    started=perf_counter()
    fact_request=looks_like_fact_request(data.message)
    price_request=asks_final_price_or_discount(data.message)
    # Explicit human requests, policy price refusal, and factual lookups do not
    # need (or trust) a local model classification. No latency penalty.
    deterministic_intent=('human' if wants_human(data.message) else
        'project_facts' if price_request or fact_request else None)
    if deterministic_intent:
        decision=AgentDecision(intent=deterministic_intent, concern_type='none',
            evidence_kind='unknown', evidence_quote='', reply='',
            needs_human=deterministic_intent=='human')
        agent_mode='local_policy'
    else:
        pre_routed=fast_route(data.message)
        try:
            decision,agent_mode=(pre_routed,'local_policy') if pre_routed is not None else decide(data.message,language,project.name)
        except LocalAgentUnavailable:
            # Model failures must reach a human review queue, not silently die.
            record_handoff(db,lead,reason='model_unavailable')
            flag_ai_review(db,lead.id,message.id,'model_unavailable')
            unavailable=translated_reply(language,'unavailable')+' '+human_reply(language,lead.contact_consent)
            claimed = accepted_ticket_locked(db, lead_id)
            if claimed:
                db.commit()
                return {'message_id':message.id, 'reply':None,
                        'ai_status':'human_takeover',
                        'message':'Saved for the assigned salesperson.',
                        'ticket_reference':claimed.reference,
                        'human_handoff_available':False}
            answer=Message(id=uid(),lead_id=lead_id,speaker='ai',body=unavailable)
            db.add(answer)
            db.commit()
            return {'message_id':message.id,'reply_id':answer.id,'ai_status':'unavailable',
                    'reply':unavailable,'message':unavailable,'human_handoff_available':True,
                    'handoff_requested':True,'response_language':language,
                    'reply_strategy':'unavailable','build':CHAT_FIX_BUILD,'hesitation':None}
    decision=route_latest_message(decision,data.message)
    verified=allowed_facts({k:v.fact_value for k,v in approved_facts(db,project.id).items()})
    response,grounding=safe_response(decision,data.message,project,verified,language=language)
    strategy='server_controlled'
    options=_next_available_slots(db,lead.project_id) if decision.intent=='booking' else []
    handoff=False
    review_reason=None
    if price_request:
        handoff=True
        review_reason='final_price_request'
        response=final_price_reply(language,lead.contact_consent)
        grounding='no_final_price_or_discount'
    elif decision.intent=='human' or decision.needs_human:
        handoff=True
        review_reason='human_requested'
        response=human_reply(language,lead.contact_consent)
        grounding='human_handoff_recorded'
    elif decision.intent=='project_facts':
        relevant,missing=fact_result(data.message,verified)
        if missing:
            handoff=True
            review_reason='missing_approved_fact'
            response=missing_fact_reply(language,lead.contact_consent)
            if not verified and language=='en':
                response='The detailed project fact sheet has not been published yet. '+response
            grounding='limited_verified_facts'  # Kept for V7 clients.
            strategy='server_controlled'
        # With a relevant fact, safe_response only reads verified dictionary.
    elif decision.intent=='booking':
        response=translated_reply(language,'slots' if options else 'no_slots')
        grounding='booking_options_only_not_confirmed'
    elif agent_mode in ('local_model','local_policy') and eligible_for_contextual_reply(decision,data.message):
        try:
            response=draft_contextual_reply(data.message,language,decision,history)
            grounding='contextual_dialogue_guarded'
            strategy='local_model_contextual'
        except LocalAgentUnavailable:
            strategy='server_template_fallback'
            review_reason='contextual_model_fallback'
    if decision.concern_type!='none' and decision.evidence_quote:
        db.add(Concern(id=uid(),lead_id=lead_id,source_message_id=message.id,
            category=decision.concern_type,evidence_kind=decision.evidence_kind,
            evidence_quote=decision.evidence_quote))
        review_reason=review_reason or 'buyer_concern'
    if handoff:
        record_handoff(db,lead,reason=review_reason or 'ai_handoff')
    if review_reason:
        flag_ai_review(db,lead.id,message.id,review_reason)
    # Commit the AI reply, human escalation and review flag together. If this
    # fails, never tell the buyer a handoff was recorded.
    claimed = accepted_ticket_locked(db, lead_id)
    if claimed:
        db.commit()
        return {'message_id':message.id, 'reply':None,
                'ai_status':'human_takeover',
                'message':'Saved for the assigned salesperson.',
                'ticket_reference':claimed.reference,
                'human_handoff_available':False}
    answer=Message(id=uid(),lead_id=lead_id,speaker='ai',body=response)
    db.add(answer)
    db.commit()
    return {'message_id':message.id,'reply_id':answer.id,'ai_status':agent_mode,
            'reply':response,'response_language':language,'build':CHAT_FIX_BUILD,
            'reply_strategy':strategy,'context_turns_used':len(history) if strategy=='local_model_contextual' else 0,
            'latency_ms':round((perf_counter()-started)*1000),'grounding_status':grounding,
            'human_handoff_available':True,'handoff_requested':handoff,
            'review_flagged':bool(review_reason),'fact_resolution':'missing_fact_escalated' if review_reason=='missing_approved_fact' else None,'booking_options':options,
            'confirmation_required':decision.intent=='booking',
            'hesitation':({'category':decision.concern_type,'evidence':decision.evidence_quote,
                           'certainty':decision.evidence_kind} if decision.concern_type!='none' else None)}


@app.get('/api/v1/buyer/hesitation')
def buyer_hesitation(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    own_lead(db,lead_id)
    return {'barriers':[{'category':c.category,'source_message_id':c.source_message_id,
                        'evidence':c.evidence_quote,'certainty':c.evidence_kind}
                       for c in db.scalars(select(Concern).where(Concern.lead_id==lead_id).order_by(Concern.created_at)).all()]}

@app.get('/api/v1/sales/leads/{lead_id}/hesitation')
def sales_hesitation(lead_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    own_lead(db,lead_id)
    return {'lead_id':lead_id,'barriers':[{'category':c.category,'source_message_id':c.source_message_id,
                        'evidence':c.evidence_quote,'certainty':c.evidence_kind}
                       for c in db.scalars(select(Concern).where(Concern.lead_id==lead_id).order_by(Concern.created_at)).all()]}


# Milestone 3: real sales workspace endpoints (all protected by sales role).
from collections import defaultdict
from statistics import median
from datetime import timedelta

@app.get('/api/v1/sales/leads/{lead_id}/messages')
def sales_messages(lead_id: str, user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    own_lead(db, lead_id)
    items=db.scalars(select(Message).where(Message.lead_id==lead_id).order_by(Message.created_at)).all()
    return [{'message_id':m.id,'speaker':m.speaker,'message':m.body,'created_at':m.created_at.isoformat()} for m in items]

@app.patch('/api/v1/sales/leads/{lead_id}/assign')
def sales_assign(lead_id: str, payload: dict, user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    l=own_lead(db,lead_id)
    if (ticket_for_lead(db,lead_id) and ticket_for_lead(db,lead_id).status in ('accepted','resolved')):
        raise HTTPException(409,'Accepted ticket ownership cannot be changed using lead assignment')
    # Only registered sales users may be assigned. No implied buyer contact permission.
    assignee=payload.get('user_id')
    if not isinstance(assignee,str) or not db.get(SalesUser, assignee):
        raise HTTPException(422,'Select a valid sales user')
    l.assigned_user_id=assignee
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='lead_assigned',subject_id=l.id))
    db.commit()
    return {'lead_id':l.id,'assigned_user_id':assignee,'contact_consent':l.contact_consent}

@app.get('/api/v1/sales/users')
def sales_users(user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    return [{'id':u.id,'display_name':u.display_name} for u in db.scalars(select(SalesUser).order_by(SalesUser.display_name)).all()]

@app.patch('/api/v1/sales/bookings/{booking_id}/attendance')
def sales_attendance(booking_id: str, payload: dict, user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    outcome=payload.get('status')
    if outcome not in ('attended','no_show'):
        raise HTTPException(422,'status must be attended or no_show')
    b=db.scalar(select(Booking).where(Booking.id==booking_id).with_for_update())
    if not b:raise HTTPException(404,'Visit not found')
    if b.status not in ('confirmed','attended','no_show'):
        raise HTTPException(409,'Cannot record attendance for this booking')
    slot=db.get(Slot,b.slot_id)
    start=slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=timezone.utc)
    if start>now():raise HTTPException(409,'Cannot record attendance before the visit starts')
    b.status=outcome
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='visit_'+outcome,subject_id=b.id))
    db.commit()
    return serialize_booking(db,b)

@app.get('/api/v1/sales/dashboard/overview')
def sales_dashboard(user_id: Annotated[str, Depends(sales)], db: Annotated[Session, Depends(get_db)]):
    leads=db.scalars(select(Lead)).all()
    bookings=db.scalars(select(Booking)).all()
    messages=db.scalars(select(Message).order_by(Message.created_at)).all()
    first_ai={}
    first_buyer={}
    for m in messages:
        if m.speaker=='buyer':first_buyer.setdefault(m.lead_id,m.created_at)
        if m.speaker in ('ai','sales'):first_ai.setdefault(m.lead_id,m.created_at)
    mins=[]
    for lead_id,start in first_buyer.items():
        end=first_ai.get(lead_id)
        if end and end>=start:mins.append((end-start).total_seconds()/60)
    month_start=now().replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    leads_this_month=sum(1 for l in leads if (l.created_at.replace(tzinfo=timezone.utc) if l.created_at.tzinfo is None else l.created_at)>=month_start)
    booked_ids={b.lead_id for b in bookings if b.status in ('confirmed','attended','no_show')}
    attended_ids={b.lead_id for b in bookings if b.status=='attended'}
    sources=defaultdict(lambda:{'leads':0,'booked':0,'attended':0})
    for l in leads:
        row=sources[l.source];row['leads']+=1
        row['booked']+=int(l.id in booked_ids);row['attended']+=int(l.id in attended_ids)
    overdue=sum(1 for l in leads if l.id not in first_ai and (now()-(l.created_at if l.created_at.tzinfo else l.created_at.replace(tzinfo=timezone.utc)))>timedelta(hours=48))
    return {'leads_total':len(leads),'leads_this_month':leads_this_month,'booked_visits':len([b for b in bookings if b.status in ('confirmed','attended','no_show')]),'attended_visits':len([b for b in bookings if b.status=='attended']),'handoff_pending':sum(l.status=='handoff_requested' and l.assigned_user_id is None for l in leads),'median_first_response_minutes':round(median(mins),1) if mins else None,'response_sample_size':len(mins),'unreplied_over_48h':overdue,'sources':[{'source':k,**v} for k,v in sorted(sources.items())]}


# Milestone 5 — persistent fact-sheet review and mocked consent-aware reminders.
class FactProposal(BaseModel):
    key: str = Field(min_length=3,max_length=100,pattern=r'^[a-z][a-z0-9_]*$')
    value: str = Field(min_length=1,max_length=700)

class SlotEnabledUpdate(BaseModel):
    enabled: bool

@app.get('/api/v1/projects/{project_id}/facts')
def public_project_facts(project_id:str,db:Annotated[Session,Depends(get_db)]):
    ensure_project(db,project_id)
    return {'project_id':project_id,'facts':[serialize_fact(v) for v in approved_facts(db,project_id).values()]}

@app.get('/api/v1/sales/projects/{project_id}/facts')
def sales_project_facts(project_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    if not db.get(Project,project_id): raise HTTPException(404,'Project not found')
    history=db.scalars(select(ProjectFactRevision).where(ProjectFactRevision.project_id==project_id)
                       .order_by(ProjectFactRevision.created_at.desc(),ProjectFactRevision.id.desc())).all()
    return {'project_id':project_id,'is_sales_head':is_sales_head(db.get(SalesUser,user_id)),
            'approved':[serialize_fact(v) for v in approved_facts(db,project_id).values()],
            'history':[serialize_fact(f) for f in history]}

@app.post('/api/v1/sales/projects/{project_id}/facts',status_code=201)
def propose_fact(project_id:str,payload:FactProposal,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    if not db.get(Project,project_id): raise HTTPException(404,'Project not found')
    pending=db.scalar(select(ProjectFactRevision).where(ProjectFactRevision.project_id==project_id,
                      ProjectFactRevision.fact_key==payload.key,ProjectFactRevision.status=='pending'))
    if pending:raise HTTPException(409,'A proposal for this fact key is already pending')
    fact=ProjectFactRevision(id=uid(),project_id=project_id,fact_key=payload.key,
                             fact_value=payload.value.strip(),status='pending',created_by=user_id)
    db.add(fact)
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='fact_proposed',subject_id=fact.id))
    db.commit()
    return serialize_fact(fact)

@app.post('/api/v1/sales/facts/{fact_id}/review')
def review_fact(fact_id:str,payload:dict,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    require_sales_head(db,user_id)
    action=payload.get('action')
    if action not in ('approve','reject'):raise HTTPException(422,'action must be approve or reject')
    fact=db.scalar(select(ProjectFactRevision).where(ProjectFactRevision.id==fact_id).with_for_update())
    if not fact:raise HTTPException(404,'Fact proposal not found')
    if fact.status!='pending':raise HTTPException(409,'Fact already reviewed')
    fact.status='approved' if action=='approve' else 'rejected'
    fact.reviewed_by=user_id;fact.reviewed_at=now()
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='fact_'+fact.status,subject_id=fact.id))
    db.commit()
    return serialize_fact(fact)

@app.get('/api/v1/sales/projects/{project_id}/slots')
def sales_project_slots(project_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    if not db.get(Project,project_id): raise HTTPException(404,'Project not found')
    rows=db.scalars(select(Slot).where(Slot.project_id==project_id,Slot.starts_at>now())
                    .order_by(Slot.starts_at).limit(100)).all()
    return [{'slot_id':s.id,'project_id':s.project_id,'starts_at':s.starts_at.isoformat(),
             'ends_at':s.ends_at.isoformat(),'enabled':s.enabled} for s in rows]

@app.patch('/api/v1/sales/slots/{slot_id}')
def toggle_slot(slot_id:str,payload:SlotEnabledUpdate,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    require_sales_head(db,user_id)
    slot=db.scalar(select(Slot).where(Slot.id==slot_id).with_for_update())
    if not slot:raise HTTPException(404,'Slot not found')
    if not payload.enabled and db.scalar(select(Booking.id).where(Booking.slot_id==slot_id,Booking.status=='confirmed')):
        raise HTTPException(409,'Cannot disable a confirmed visit slot')
    slot.enabled=payload.enabled
    db.add(AuditEvent(id=uid(),actor_id=user_id,event='slot_updated',subject_id=slot_id))
    db.commit()
    return {'slot_id':slot.id,'enabled':slot.enabled}

@app.get('/api/v1/sales/reminders')
def sales_reminders(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    items=db.scalars(select(ReminderOutbox).order_by(ReminderOutbox.due_at.desc()).limit(100)).all()
    return [{'id':r.id,'booking_id':r.booking_id,'kind':r.kind,'due_at':r.due_at.isoformat(),
             'status':r.status,'processed_at':r.processed_at.isoformat() if r.processed_at else None}
            for r in items]
