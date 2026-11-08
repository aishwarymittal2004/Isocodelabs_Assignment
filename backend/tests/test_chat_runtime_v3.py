from types import SimpleNamespace
from app.agent import AgentDecision, ground_obvious_concern, decide, safe_response

PROJECT=SimpleNamespace(name='Aranya',city='Ahmedabad',price_min_inr=6500000,price_max_inr=12000000,rera_registration=None)

def test_language_switch_does_not_require_ollama(monkeypatch):
    monkeypatch.setenv('SITEPILOT_MODEL_URL','https://not-allowed.example:443')
    monkeypatch.setenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK','false')
    msg='Kya aap hindi me baat kr skte h?'
    decision, mode=decide(msg,'hi','Aranya')
    reply, status=safe_response(decision,msg,PROJECT,language='hi')
    assert mode=='local_policy'
    assert status=='language_preference_acknowledged'
    assert 'हिंदी' in reply

def test_family_hesitation_overrides_misclassified_project_facts():
    msg='I am interested in one of your project but my wife is not happy with the project'
    decision=AgentDecision(intent='project_facts',concern_type='none',evidence_kind='unknown',evidence_quote='',reply='')
    d=ground_obvious_concern(decision,msg)
    reply, source=safe_response(d,msg,PROJECT)
    assert d.concern_type=='family' and source=='concern_acknowledged'
    assert 'wife' in reply


def test_neutral_family_message_not_forced_into_hesitation():
    msg='My wife and I would like to book a visit.'
    decision=AgentDecision(intent='booking',concern_type='none',evidence_kind='unknown',evidence_quote='',reply='')
    assert ground_obvious_concern(decision,msg).intent=='booking'

def test_http_chat_uses_corrected_runtime(tmp_path, monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/runtime.db')
    monkeypatch.setenv('JWT_SECRET','test-only-secret-with-at-least-32-characters')
    monkeypatch.setenv('DEMO_SALES_EMAIL','reviewer@example.test')
    monkeypatch.setenv('DEMO_SALES_PASSWORD','test-password')
    monkeypatch.setenv('SALES_HEAD_EMAIL','reviewer@example.test')
    monkeypatch.setenv('SITEPILOT_ALLOW_CLASSIFIER_FALLBACK','false')
    import app.core, app.models, app.main, app.seed
    importlib.reload(app.core)
    importlib.reload(app.models)
    import app.tickets_models, app.ticket_flow, app.tickets_router
    importlib.reload(app.tickets_models)
    importlib.reload(app.ticket_flow)
    importlib.reload(app.tickets_router)
    importlib.reload(app.main)
    importlib.reload(app.seed)
    app.seed.seed()
    with TestClient(app.main.app) as c:
        assert c.get('/health').json()['build']=='sitepilot-reliability-v7.2'
        session=c.post('/api/v1/leads',json={'name':'Demo Buyer','phone':'9000000751','project_id':'project-1','source':'website','contact_consent':False}).json()
        headers={'Authorization':'Bearer '+session['buyer_session_token']}
        msg='Kya aap hindi me baat kr skte h?'
        result=c.post('/api/v1/buyer/conversations/messages',headers=headers,json={'message':msg,'language':'en'})
        assert result.status_code==200,result.text
        body=result.json()
        assert body['response_language']=='hi' and 'हिंदी' in body['reply']
        assert body['build']=='sitepilot-reliability-v7.2'
        # Simulate an incorrectly classified local model; server must still honor explicit family evidence.
        from app.agent import AgentDecision
        monkeypatch.setattr(app.main,'decide',lambda m,lang,project:(AgentDecision(intent='project_facts',concern_type='none',evidence_kind='unknown',evidence_quote='',reply=''), 'local_model'))
        # Runtime must enforce its own explicit-concern override, not just trust decide().
        family='I am interested but my wife is not happy with the property'
        response=c.post('/api/v1/buyer/conversations/messages',headers=headers,json={'message':family,'language':'en'})
        assert response.status_code==200,response.text
        assert response.json()['hesitation']['category']=='family'
        assert 'wife' in response.json()['reply']


def test_http_school_concern_and_switch_back_to_english(tmp_path, monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/english.db')
    monkeypatch.setenv('JWT_SECRET','test-only-secret-with-at-least-32-characters')
    monkeypatch.setenv('DEMO_SALES_EMAIL','reviewer@example.test')
    monkeypatch.setenv('DEMO_SALES_PASSWORD','test-password')
    monkeypatch.setenv('SALES_HEAD_EMAIL','reviewer@example.test')
    import app.core, app.models, app.main, app.seed
    importlib.reload(app.core);importlib.reload(app.models)
    import app.tickets_models, app.ticket_flow, app.tickets_router
    importlib.reload(app.tickets_models)
    importlib.reload(app.ticket_flow)
    importlib.reload(app.tickets_router);importlib.reload(app.main);importlib.reload(app.seed)
    app.seed.seed()
    with TestClient(app.main.app) as client:
        data=client.post('/api/v1/leads',json={'name':'Test Buyer','phone':'9000000752','project_id':'project-1','source':'website','contact_consent':False}).json()
        headers={'Authorization':'Bearer '+data['buyer_session_token']}
        # Emulate model incorrectly choosing a generic property response.
        monkeypatch.setattr(app.main, 'decide', lambda m,lang,name:(AgentDecision(intent='general',concern_type='none',evidence_kind='unknown',reply=''),'local_model'))
        message='My wife is worried because the school is too far away and our child is only five years old.'
        result=client.post('/api/v1/buyer/conversations/messages',headers=headers,json={'message':message,'language':'hi'})
        assert result.status_code==200, result.text
        assert result.json()['hesitation']['category']=='location'
        assert 'स्कूल' in result.json()['reply']
        english=client.post('/api/v1/buyer/conversations/messages',headers=headers,json={'message':'Reply in english','language':'hi'})
        assert english.status_code==200, english.text
        assert english.json()['response_language']=='en'
        assert english.json()['grounding_status']=='language_preference_acknowledged'
        assert 'continue in English' in english.json()['reply']
