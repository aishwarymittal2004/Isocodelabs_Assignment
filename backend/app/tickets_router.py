"""Ticket lifecycle APIs layered onto SitePilot's existing JWT identities."""
from __future__ import annotations
import json
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core import buyer,sales,get_db,now
from .models import Lead,Message,Project,SalesUser
from .tickets_models import BuyerTicket,TicketProject,TicketEvent
from .ticket_flow import ensure_ticket,ticket_for_lead,request_human,accept_ticket,event,uid,facts

router=APIRouter(prefix='/api/v1',tags=['ticket-workflow'])

class ProjectAttach(BaseModel):
    project_id:str
class StaffReply(BaseModel):
    message:str=Field(min_length=1,max_length=3000)
class CloseTicket(BaseModel):
    note:str=Field(min_length=3,max_length=1000)

def own_buyer(db,id):
    lead=db.get(Lead,id)
    if lead is None:raise HTTPException(404,'Enquiry not found')
    return lead

def get_ticket(db,tid):
    ticket=db.get(BuyerTicket,tid)
    if ticket is None:raise HTTPException(404,'Ticket not found')
    return ticket

def sales_authorized(db,ticket,user_id):
    if ticket.owner_user_id==user_id:return
    # Sales head can inspect every ticket, but cannot post replies as its owner.
    from .main import require_sales_head,is_sales_head
    user=db.get(SalesUser,user_id)
    if user is None or not is_sales_head(user):raise HTTPException(403,'Not assigned to this ticket')

def serialize(db,t,contact=False):
    lead=db.get(Lead,t.lead_id)
    owner=db.get(SalesUser,t.owner_user_id) if t.owner_user_id else None
    rows=db.scalars(select(TicketProject).where(TicketProject.ticket_id==t.id)).all()
    return {'id':t.id,'reference':t.reference,'lead_id':t.lead_id,'status':t.status,
            'owner':{'name':owner.display_name,'email':owner.email} if owner else None,
            'project_ids':[r.project_id for r in rows],
            'requirements':json.loads(t.requirements_json or '{}'),
            'contact_consent':lead.contact_consent,
            'buyer_phone':lead.phone if contact and lead.contact_consent else None,
            'created_at':t.created_at.isoformat(),
            'accepted_at':t.accepted_at.isoformat() if t.accepted_at else None}

def history(db,t):
    msgs=db.scalars(select(Message).where(Message.lead_id==t.lead_id).order_by(Message.created_at,Message.id)).all()
    events=db.scalars(select(TicketEvent).where(TicketEvent.ticket_id==t.id).order_by(TicketEvent.created_at,TicketEvent.id)).all()
    combined=[{'type':'message','id':m.id,'speaker':m.speaker,'text':m.body,'at':m.created_at.isoformat()} for m in msgs]
    combined.extend({'type':'event','id':e.id,'kind':e.kind,'text':e.detail,'at':e.created_at.isoformat()} for e in events)
    return sorted(combined,key=lambda item:(item['at'],item['type'],item['id']))

@router.get('/buyer/ticket')
def buyer_ticket(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    t=ensure_ticket(db,own_buyer(db,lead_id));db.commit();return serialize(db,t)

@router.get('/buyer/ticket/history')
def buyer_ticket_history(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    t=ensure_ticket(db,own_buyer(db,lead_id));db.commit();return {'reference':t.reference,'entries':history(db,t)}

@router.get('/buyer/ticket/export')
def buyer_ticket_export(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    t=ensure_ticket(db,own_buyer(db,lead_id));db.commit()
    entries=history(db,t)
    lead=db.get(Lead,t.lead_id)
    text='SitePilot enquiry '+t.reference+'\nBuyer: '+lead.name+'\nStatus: '+t.status+'\n\n'+'\n'.join(
        x['at']+' | '+(x.get('speaker') or x.get('kind','event'))+': '+x['text'] for x in entries)
    return Response(text,media_type='text/plain; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="{t.reference}.txt"'})

@router.post('/buyer/ticket/projects')
def add_ticket_project(data:ProjectAttach,lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    lead=own_buyer(db,lead_id);ticket=ensure_ticket(db,lead)
    p=db.get(Project,data.project_id)
    if not p or not p.facts_approved:raise HTTPException(404,'Published project not found')
    already=db.get(TicketProject,(ticket.id,p.id))
    if not already:
        db.add(TicketProject(ticket_id=ticket.id,project_id=p.id))
        event(db,ticket,'project_added',actor_type='buyer',detail=p.name)
    db.commit();return serialize(db,ticket)

@router.get('/buyer/ticket/projects')
def ticket_project_summary(lead_id:Annotated[str,Depends(buyer)],db:Annotated[Session,Depends(get_db)]):
    ticket=ensure_ticket(db,own_buyer(db,lead_id));db.commit()
    rows=db.scalars(select(TicketProject).where(TicketProject.ticket_id==ticket.id)).all()
    result=[]
    for r in rows:
        project=db.get(Project,r.project_id)
        if not project or not project.facts_approved:continue
        result.append({'id':project.id,'name':project.name,'facts':facts(db,project.id)})
    return {'ticket_reference':ticket.reference,'projects':result,'source':'approved_revisions_only'}

@router.get('/sales/tickets/queue')
def ticket_queue(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    # Reflect handoffs generated by the pre-existing V8 approved-fact policy.
    legacy=db.scalars(select(Lead).where(Lead.status=='handoff_requested',Lead.assigned_user_id.is_(None))).all()
    for lead in legacy:
        ticket=ensure_ticket(db,lead)
        if ticket.status=='ai_active':request_human(db,lead,'Existing V8 handoff awaiting owner')
    db.commit()
    rows=db.scalars(select(BuyerTicket).where(BuyerTicket.status=='pending',BuyerTicket.owner_user_id.is_(None))
                    .order_by(BuyerTicket.created_at).limit(100)).all()
    return [serialize(db,t) for t in rows]

@router.get('/sales/tickets/mine')
def my_sales_tickets(user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    rows=db.scalars(select(BuyerTicket).where(BuyerTicket.owner_user_id==user_id)
                    .order_by(BuyerTicket.created_at.desc()).limit(100)).all()
    return [serialize(db,t) for t in rows]

@router.get('/sales/tickets/{ticket_id}')
def sales_ticket(ticket_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    t=get_ticket(db,ticket_id);sales_authorized(db,t,user_id)
    return {'ticket':serialize(db,t,contact=True),'history':history(db,t)}

@router.post('/sales/tickets/{ticket_id}/accept')
def accept_sales_ticket(ticket_id:str,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    t=get_ticket(db,ticket_id)
    try:
        accept_ticket(db,own_buyer(db,t.lead_id),user_id)
        db.commit()
    except Exception:
        db.rollback();raise
    return serialize(db,t)

@router.post('/sales/tickets/{ticket_id}/messages',status_code=201)
def post_sales_message(ticket_id:str,data:StaffReply,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    t=db.scalar(select(BuyerTicket).where(BuyerTicket.id==ticket_id).with_for_update())
    if not t:raise HTTPException(404,'Ticket not found')
    if t.status!='accepted' or t.owner_user_id!=user_id:
        raise HTTPException(403,'Only the accepting salesperson can reply')
    msg=Message(id=uid(),lead_id=t.lead_id,speaker='sales',body=data.message.strip())
    db.add(msg);event(db,t,'sales_reply',actor_type='sales',actor_id=user_id,detail='Salesperson replied')
    db.commit();return {'message_id':msg.id,'ticket_reference':t.reference,'status':'saved'}

@router.post('/sales/tickets/{ticket_id}/resolve')
def resolve_ticket(ticket_id:str,data:CloseTicket,user_id:Annotated[str,Depends(sales)],db:Annotated[Session,Depends(get_db)]):
    t=db.scalar(select(BuyerTicket).where(BuyerTicket.id==ticket_id).with_for_update())
    if not t:raise HTTPException(404,'Ticket not found')
    if t.owner_user_id!=user_id or t.status!='accepted':
        raise HTTPException(403,'Only the accepting salesperson may resolve this ticket')
    t.status='resolved';t.resolved_at=now();t.updated_at=now()
    event(db,t,'resolved',actor_type='sales',actor_id=user_id,detail=data.note)
    db.commit();return serialize(db,t)
