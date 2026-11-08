"""Single-ticket ownership and approved-facts-only cross-project buyer assistance.

No external LLM calls or speculative property facts in this module.
"""
from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from .core import now
from .models import Lead, Project, ProjectFactRevision, Message, SalesUser, AuditEvent
from .tickets_models import BuyerTicket, TicketProject, TicketEvent, TicketNotification


def uid(): return str(uuid.uuid4())


def ensure_ticket(db, lead:Lead):
    # Serialize legacy ticket creation on the parent lead row for PostgreSQL concurrency.
    db.scalar(select(Lead).where(Lead.id==lead.id).with_for_update())
    ticket=db.scalar(select(BuyerTicket).where(BuyerTicket.lead_id==lead.id))
    if ticket:
        return ticket
    # Legacy V8 leads may already have requested or accepted a handoff.
    # Preserve that existing ownership; never accidentally restart AI on them.
    legacy_accepted=bool(lead.assigned_user_id and lead.status in ('handoff_requested','human_accepted'))
    starting_status='accepted' if legacy_accepted else 'pending' if lead.status=='handoff_requested' else 'ai_active'
    ticket=BuyerTicket(id=uid(), reference='SP-'+secrets.token_hex(5).upper(), lead_id=lead.id,
                       status=starting_status,owner_user_id=lead.assigned_user_id if legacy_accepted else None,
                       accepted_at=now() if legacy_accepted else None,requirements_json='{}')
    db.add(ticket)
    db.flush()
    db.add(TicketProject(ticket_id=ticket.id,project_id=lead.project_id))
    db.add(TicketEvent(id=uid(),ticket_id=ticket.id,kind='created',actor_type='system',detail='Enquiry created'))
    db.flush()
    return ticket


def ticket_for_lead(db, lead_id, lock=False):
    stmt=select(BuyerTicket).where(BuyerTicket.lead_id==lead_id)
    if lock: stmt=stmt.with_for_update()
    return db.scalar(stmt)


def event(db,ticket,kind,actor_type='system',actor_id=None,detail=None):
    db.add(TicketEvent(id=uid(),ticket_id=ticket.id,kind=kind,actor_type=actor_type,
                       actor_id=actor_id,detail=(detail or '')[:1000]))


def request_human(db,lead:Lead,reason='Buyer requested a salesperson'):
    ticket=ensure_ticket(db,lead)
    ticket=db.scalar(select(BuyerTicket).where(BuyerTicket.id==ticket.id).with_for_update())
    if ticket.status in ('accepted','resolved'):
        return ticket
    if ticket.status!='pending':
        ticket.status='pending'; ticket.updated_at=now()
        lead.status='handoff_requested'
        event(db,ticket,'handoff_requested',detail=reason)
        db.add(TicketNotification(id=uid(),ticket_id=ticket.id,kind='sales_queue',state='pending',
                                  note='Internal queue notification only; no external message sent'))
    db.flush()
    return ticket


def accept_ticket(db,lead:Lead,user_id):
    # Compare-and-swap makes exactly one successful claimant, even if two HTTP
    # requests reach PostgreSQL at nearly the same instant. The losing request
    # gets HTTP 409; only the winner creates assignment and audit history.
    ticket=ensure_ticket(db,lead)
    user=db.get(SalesUser,user_id)
    if not user: raise HTTPException(403,'Sales account unavailable')
    timestamp=now()
    stmt=(update(BuyerTicket)
          .where(BuyerTicket.id==ticket.id,BuyerTicket.status=='pending',
                 BuyerTicket.owner_user_id.is_(None))
          .values(owner_user_id=user_id,status='accepted',accepted_at=timestamp,updated_at=timestamp)
          .returning(BuyerTicket.id))
    won=db.scalar(stmt)
    if won is None:
        raise HTTPException(409,'Ticket already accepted or not awaiting handoff')
    lead.assigned_user_id=user_id;lead.status='human_accepted'
    event(db,ticket,'accepted',actor_type='sales',actor_id=user_id,detail='Owner accepted; buyer-facing AI disabled')
    db.add(TicketNotification(id=uid(),ticket_id=ticket.id,kind='buyer_acceptance',state='pending',
                              note='Buyer sees acceptance in app; external delivery not configured'))
    db.flush()
    return db.get(BuyerTicket,ticket.id, populate_existing=True)


def accepted_ticket_locked(db,lead_id):
    t=ticket_for_lead(db,lead_id,lock=True)
    return t if t and t.status in ('accepted','resolved') else None


def facts(db,project_id):
    result={}
    revisions=db.scalars(select(ProjectFactRevision).where(
        ProjectFactRevision.project_id==project_id,
        ProjectFactRevision.status=='approved').order_by(
        ProjectFactRevision.created_at,ProjectFactRevision.id)).all()
    for r in revisions:
        key=r.fact_key.lower()
        if any(word in key for word in ('final_price','final_quote','discount','negotiated')):continue
        result[r.fact_key]=r.fact_value
    return result


def extract_requirements(message):
    text=message.lower()
    fields={}
    bhk=re.search(r'\b([1-6])\s*bhk\b',text)
    if bhk:fields['configuration']=bhk.group(1)+' BHK'
    amt=re.search(r'(?:budget\s*(?:of|is|around|under|within|upto|up to)?\s*|under\s*|within\s*|₹\s*)(?:rs\.?\s*)?(?:₹\s*)?([\d,.]+)\s*(lakh|lakhs|lac|lacs|crore|cr)\b',text)
    if amt:
        try:
            v=float(amt.group(1).replace(',','')); unit=10_000_000 if amt.group(2) in ('crore','cr') else 100_000
            fields['budget_inr']=int(v*unit)
        except ValueError:pass
    for word in ('school','hospital','metro','transport','parking'):
        if word in text: fields[word+'_priority']=True
    sq=re.search(r'\b(\d{2,5})\s*(?:sq\.?\s*ft|sqft|square\s*feet)\b',text)
    if sq:fields['area_sqft']=int(sq.group(1))
    return fields


def updated_requirements(db,ticket,message):
    data=json.loads(ticket.requirements_json or '{}')
    additions=extract_requirements(message)
    if data.get('awaiting_area') and not additions and 2 <= len(message.strip()) <= 60:
        # Short follow-up answers must not get lost in the intent classifier.
        if not re.fullmatch(r'(?i)(yes|no|ok|okay|sure|maybe)',message.strip()):
            additions['preferred_area']=message.strip()
            data.pop('awaiting_area',None)
    if additions:
        data.update(additions)
        ticket.requirements_json=json.dumps(data,sort_keys=True)
        ticket.updated_at=now()
        event(db,ticket,'requirements_updated',actor_type='buyer',detail=', '.join(additions.keys()))
    return data


def approved_projects(db):
    return db.scalars(select(Project).where(Project.facts_approved.is_(True)).order_by(Project.name)).all()


def approved_minimum_price_inr(facts_map):
    """Conservatively parse only an *approved, indicative* lower price bound.

    Does not infer prices from legacy Project.price_min_inr or market estimates.
    """
    import re
    for key,value in facts_map.items():
        name=key.lower()
        if not any(term in name for term in ('price_range','indicative_price','advertised_price','price_min')):
            continue
        text=str(value).lower().replace(',','')
        # A structured numeric price_min key is unambiguous.
        if name=='price_min_inr' and text.isdigit():return int(text)
        pattern=r'(?:₹|inr|rs\.?|starting from|from)\s*([\d.]+)\s*(crore|crores|cr|lakh|lakhs|lac)'
        m=re.search(pattern,text)
        if m:
            factor=10_000_000 if m.group(2) in ('crore','crores','cr') else 100_000
            try:return int(float(m.group(1))*factor)
            except ValueError:pass
    return None

def comparable_projects(db,requirements):
    """Conservative suitability check: no numeric claim without approved facts."""
    budget=requirements.get('budget_inr')
    configuration=requirements.get('configuration','')
    options=[];over_budget=[];unverified=[]
    for p in approved_projects(db):
        f=facts(db,p.id)
        if not f:
            unverified.append(p.name);continue
        config_text=' '.join(str(v) for k,v in f.items() if any(kword in k for kword in ('configuration','property_type','unit_type'))).lower()
        if configuration and config_text and configuration.lower().replace(' ','') not in config_text.replace(' ',''):
            continue
        minimum=approved_minimum_price_inr(f)
        if budget and minimum and minimum>budget:
            over_budget.append(p.name);continue
        if budget and minimum is None:
            unverified.append(p.name);continue
        options.append(p.name)
    return options,over_budget,unverified

def short_list(db,ticket,lead,requirements):
    projects=approved_projects(db)
    budget=requirements.get('budget_inr')
    config=requirements.get('configuration','')
    matches=[];incomplete=[]
    for p in projects:
        f=facts(db,p.id)
        if not f:continue
        # Price parsing must come from an approved fact only, not Project legacy sample numbers.
        price_text=' '.join(str(v) for k,v in f.items() if 'price' in k or 'budget' in k)
        # Without a structured approved price minimum, do not claim that a property meets the budget.
        # Likewise never infer configuration from a project name alone.
        config_text=' '.join(str(v) for k,v in f.items() if 'configuration' in k or 'property_type' in k)
        if config and config.lower().replace(' ','') not in config_text.lower().replace(' ',''):
            continue
        missing=[]
        if budget is not None: missing.append('verified numeric price comparison')
        for k in ('school_priority','hospital_priority','metro_priority','transport_priority'):
            if requirements.get(k):missing.append(k.replace('_priority','')+' proximity')
        if missing:incomplete.append(p.name)
        else:matches.append(p.name)
    return matches,incomplete


def save_assisted_reply(db,lead,original,reply,reason=None,missing=False):
    t=ensure_ticket(db,lead)
    buyer_msg=Message(id=uid(),lead_id=lead.id,speaker='buyer',body=original)
    db.add(buyer_msg);db.flush()  # Parent FK must exist before review/audit rows.
    if missing:
        request_human(db,lead,reason or 'No approved comparable property facts')
    # Serialize the final reply against accept_ticket's row lock.
    t=db.scalar(select(BuyerTicket).where(BuyerTicket.id==t.id).with_for_update())
    if t.status in ('accepted','resolved'):
        db.commit()
        return {'message_id':buyer_msg.id,'reply':None,'ai_status':'human_takeover','ticket_reference':t.reference}
    ai_msg=Message(id=uid(),lead_id=lead.id,speaker='ai',body=reply)
    db.add(ai_msg);db.commit()
    return {'message_id':buyer_msg.id,'reply_id':ai_msg.id,'reply':reply,'ai_status':'ticket_policy',
            'grounding_status':'approved_database_only','ticket_reference':t.reference,
            'human_handoff_available':True,'booking_options':[],'confirmation_required':False}


def handle_ticket_message(db,lead:Lead,message:str):
    ticket=ensure_ticket(db,lead)
    if lead.status=='handoff_requested' and ticket.status=='ai_active':
        ticket=request_human(db,lead,'Existing AI review requested human assistance')
    # Ensure a full takeover is honored even when customer posts via the old chat endpoint.
    if ticket.status in ('accepted','resolved'):
        msg=Message(id=uid(),lead_id=lead.id,speaker='buyer',body=message)
        db.add(msg);db.commit()
        return {'message_id':msg.id,'reply':None,'ai_status':'human_takeover',
                'ticket_reference':ticket.reference,'human_handoff_available':False,
                'message':'Your message was saved for your assigned salesperson.'}
    req=updated_requirements(db,ticket,message)
    lowered=message.lower().strip()
    # A request to compare attached projects should not require a budget first.
    if re.search(r'\b(?:compare|comparison|difference|versus|vs\.?)\b',lowered):
        rows=db.scalars(select(TicketProject).where(TicketProject.ticket_id==ticket.id)).all()
        attached=[db.get(Project,r.project_id) for r in rows]
        attached=[p for p in attached if p and p.facts_approved]
        if len(attached)>=2:
            lines=['Here are the approved facts for the projects on your ticket:']
            missing=False
            for p in attached[:6]:
                data=facts(db,p.id)
                lines.append('\n'+p.name+':')
                if not data:
                    lines.append('• No approved details published.');missing=True
                else:
                    for k,v in list(data.items())[:7]:
                        lines.append('• '+k.replace('_',' ').title()+': '+v)
            lines.append('I will not assume unknown prices, distances, or availability.')
            return save_assisted_reply(db,lead,message,'\n'.join(lines),missing=missing,
                                       reason='Comparison includes a project without approved facts')
    # Greeting/general questions still flow to the existing V8 classifier.
    if any(x in lowered for x in ('looks shady','seems shady','scam','fraud','is it legit','legitimate','real rera','rera verified')):
        p=db.get(Project,lead.project_id)
        safe_facts=facts(db,lead.project_id)
        rera=safe_facts.get('rera_registration') or safe_facts.get('rera_status')
        if rera:
            reply=(f'For {p.name}, the approved fact sheet states: RERA information — {rera}. '
                   'That alone does not establish the legitimacy of a project. What specific detail concerns you?')
            return save_assisted_reply(db,lead,message,reply)
        reply=('I understand why you want to verify the project before proceeding. '
               'There is no approved registration/legitimacy evidence available in our fact sheet. '
               'I have flagged this question in your existing ticket for a salesperson. '
               'What specific document or detail would you like verified?')
        return save_assisted_reply(db,lead,message,reply,missing=True,reason='Buyer seeks unverified project legitimacy evidence')
    # Read-only model-directed discovery. Ticket acceptance was checked above.
    # Sensitive operations continue through the original, backend-owned routes.
    from .discovery_integration import try_grounded_discovery
    discovery_result = try_grounded_discovery(db, lead, message)
    if discovery_result is not None:
        return save_assisted_reply(db, lead, message, discovery_result.reply)

    discovery=bool(re.search(r'\b(?:other\s+propert|alternativ|recommend|suggest|compare|refer\s+me|based\s+on\s+my\s+budget|looking\s+for|need\s+(?:a|the)\s+(?:house|home|flat)|within\s+(?:a|the)\s+budget)\b',lowered))
    request_with_constraints=bool(re.search(r'\b(?:bhk|school|hospital|budget|sqft|sq\s*ft)\b',lowered) and ('need' in lowered or 'looking' in lowered))
    if not(discovery or request_with_constraints):
        if 'preferred_area' in req and req.get('preferred_area')==message.strip():
            return save_assisted_reply(db,lead,message,
                f'Noted: your preferred area is {req["preferred_area"]}. I will only refer to published projects and their approved details. You can ask me to compare the available projects.')
        db.commit() # Persist extracted requirements on the existing ticket.
        return None
    if not req.get('budget_inr'):
        reply='What is your approximate total purchase budget? I will check only our published, approved project information.'
        return save_assisted_reply(db,lead,message,reply)
    if not req.get('configuration'):
        reply='What home configuration would you prefer (for example, 2 BHK or 3 BHK)? I will only compare verified listings.'
        return save_assisted_reply(db,lead,message,reply)
    if not req.get('preferred_area'):
        req['awaiting_area']=True
        ticket.requirements_json=json.dumps(req,sort_keys=True)
    projects=approved_projects(db)
    if not projects:
        return save_assisted_reply(db,lead,message,'We currently have no published projects to compare. I have added this to your existing ticket so a salesperson can confirm available options.',missing=True)
    options,over_budget,unverified=comparable_projects(db,req)
    lines=[f'I have noted your {req["configuration"]} preference and ₹{req["budget_inr"]:,} total budget.']
    if options:
        lines.append('Projects not ruled out by approved price/configuration information: '+', '.join(options[:8])+'. These are not confirmed matches.')
    if over_budget:
        lines.append('Projects with approved indicative minimum prices above that budget: '+', '.join(over_budget[:8])+'.')
    if unverified:
        lines.append('Projects with insufficient approved information for a reliable comparison: '+', '.join(unverified[:8])+'.')
    if not options and not unverified:
        lines.append('No suitable match can currently be confirmed from the approved inventory.')
    lines.append('I cannot verify school, hospital, or transport proximity unless it is explicitly documented in the approved database.')
    if not req.get('preferred_area'):lines.append('Which area of Ahmedabad would you prefer to search in?')
    lines.append('I have flagged unresolved comparisons on this existing ticket for a salesperson.')
    return save_assisted_reply(db,lead,message,'\n'.join(lines),missing=True,
       reason='Buyer requests a comparison with missing verified budget or proximity facts')
