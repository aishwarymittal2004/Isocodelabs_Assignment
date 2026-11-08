import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core import Base
from app.models import Project,ProjectFactRevision
from app.grounded_discovery import handle_discovery


def test_presentation_is_server_grounded(monkeypatch):
    # Use a mock catalog so this test has no DB and no Ollama dependencies.
    from app import grounded_discovery as module
    monkeypatch.setattr(module,'_approved_catalog',lambda db:[
      {'id':'a','name':'Sample Project A','facts':{'amenities':'Verified library and garden', 'price_range':'Illustrative range only'}},
      {'id':'b','name':'Sample Project B','facts':{'parking_policy':'One approved parking bay'}},
    ])
    out=handle_discovery(None,'What properties are there?',[],lambda _: {'action':'list_projects'})
    assert 'Sample Project A' in out.reply and 'Sample Project B' in out.reply
    assert 'Verified library and garden' in out.reply
    assert 'guaranteed school distance' not in out.reply


def test_new_wording_still_uses_model_plan(monkeypatch):
    from app import grounded_discovery as module
    monkeypatch.setattr(module,'_approved_catalog',lambda db:[{'id':'x','name':'Example Home','facts':{}}])
    seen=[]
    def model(payload):
        seen.append(payload)
        return {'action':'list_projects'}
    reply=handle_discovery(None,'What homes are currently on your books?',
       [{'speaker':'buyer','body':'We discussed a 2 BHK'}],model)
    assert reply.action=='list_projects'
    assert seen[0]['history'][0]['text']=='We discussed a 2 BHK'


def test_untrusted_names_and_values_cannot_be_generated(monkeypatch):
    from app import grounded_discovery as module
    monkeypatch.setattr(module,'_approved_catalog',lambda db:[{'id':'a','name':'Approved Place','facts':{'amenities':'Approved pool'}}])
    malicious={'action':'project_details','project_ids':['not_real'],'fact_keys':['fake_discount']}
    reply=handle_discovery(None,'Tell me the special price',[],lambda _:malicious)
    assert 'fake_discount' not in reply.reply and 'Approved Place' in reply.reply
    assert 'Approved pool' in reply.reply


def test_non_discovery_remains_existing_backend(monkeypatch):
    from app import grounded_discovery as module
    monkeypatch.setattr(module,'_approved_catalog',lambda db:[])
    assert handle_discovery(None,'Book my visit',[],lambda _: {'action':'not_discovery'}) is None
    assert handle_discovery(None,'What options?',[],lambda _: {'action':'invented_action'}) is None


def test_ollama_adapter_uses_structured_plan_without_property_values(monkeypatch):
    from app import grounded_discovery as module
    from app import agent
    seen=[]
    def fake_model(payload):
        seen.append(payload)
        return {'message':{'content':'{"action":"list_projects","project_ids":[],"fact_keys":[],"clarification":""}'}}
    monkeypatch.setattr(agent,'_ollama_chat',fake_model)
    plan=module.ollama_discovery_plan({'system':module.POLICY,
        'buyer_message':'What properties exist?','history':[{'role':'buyer','text':'Need 2BHK'}],
        'catalog':[{'id':'p1','name':'Demo','approved_fact_keys':['amenities']}]})
    assert plan['action']=='list_projects'
    assert seen[0]['stream'] is False
    assert 'facts' not in seen[0]['messages'][1]['content']
