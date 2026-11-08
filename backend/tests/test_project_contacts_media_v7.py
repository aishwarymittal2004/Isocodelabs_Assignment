"""Acceptance checks for project contacts / image moderation; no live Ollama needed."""
from io import BytesIO
from PIL import Image
from test_api import client, new_buyer, bearer  # reuse isolated DB/fixture


def sales_auth(c):
    r=c.post('/api/v1/auth/login',json={'email':'reviewer@example.test','password':'test-password'})
    assert r.status_code==200,r.text
    return bearer(r.json()['access_token'])


def contact(name='Nisha Shah'):
    return {'name':name,'role_title':'Senior Sales Executive','phone':'+919900001111','email':'nisha@example.com','active':True}


def test_sales_contact_approval_handoff_and_edit_hides_changed_details(client):
    auth=sales_auth(client)
    public='/api/v1/projects/project-1/salespeople'
    admin='/api/v1/sales/projects/project-1/salespeople'
    created=client.post(admin,json=contact(),headers=auth)
    assert created.status_code==201,created.text
    id=created.json()['id']
    assert created.json()['approved'] is False
    assert client.get(public).json()==[]
    b=new_buyer(client,'9555555551')
    h=client.post('/api/v1/buyer/handoff',headers=bearer(b['buyer_session_token']))
    assert h.status_code==202
    assert h.json()['salespeople']==[]
    bad=client.patch(admin+'/'+id+'/approval',json={'approved':True})
    assert bad.status_code==401
    reviewed=client.patch(admin+'/'+id+'/approval',json={'approved':True},headers=auth)
    assert reviewed.status_code==200
    assert client.get(public).json()[0]['name']=='Nisha Shah'
    assert client.get('/api/v1/buyer/handoff',headers=bearer(b['buyer_session_token'])).json()['salespeople'][0]['phone']=='+919900001111'
    updated=client.patch(admin+'/'+id,json=contact('Kavya Shah'),headers=auth)
    assert updated.status_code==200 and updated.json()['approved'] is False
    assert client.get(public).json()==[]
    assert client.get('/api/v1/projects/project-2/salespeople').json()==[]
    assert client.patch('/api/v1/sales/projects/project-2/salespeople/'+id,json=contact(),headers=auth).status_code==404


def test_project_draft_with_contact_is_private_until_approved_and_published(client):
    auth=sales_auth(client)
    payload={'name':'West Avenue','city':'Ahmedabad','description':'Unpublished sample project description.',
        'salesperson_name':'Riya Shah','salesperson_phone':'+919988776655','salesperson_email':'riya@example.com'}
    res=client.post('/api/v1/sales/projects',json=payload,headers=auth)
    assert res.status_code==201,res.text
    project_id=res.json()['id']
    assert res.json()['published'] is False
    assert all(p['id']!=project_id for p in client.get('/api/v1/projects').json())
    assert client.get('/api/v1/projects/'+project_id+'/salespeople').status_code==404
    contacts=client.get('/api/v1/sales/projects/'+project_id+'/salespeople',headers=auth).json()
    assert len(contacts)==1 and contacts[0]['approved'] is False
    assert client.post('/api/v1/sales/projects',json={'name':'Incomplete','city':'Ahmedabad','description':'A draft for later review',
            'salesperson_name':'Test'},headers=auth).status_code==422


def test_project_photo_upload_requires_auth_approval_and_valid_image(client):
    auth=sales_auth(client)
    url='/api/v1/sales/projects/project-1/images'
    public=lambda id:f'/api/v1/projects/project-1/images/{id}'
    img=Image.new('RGB',(320,200),'blue')
    out=BytesIO();img.save(out,'PNG');data=out.getvalue()
    bad=client.post(url,files={'file':('unsafe.svg',b'<svg onload="alert(1)"/>','image/svg+xml')},headers=auth)
    assert bad.status_code==415
    assert client.post(url,files={'file':('photo.png',data,'image/png')}).status_code==401
    created=client.post(url,files={'file':('photo.png',data,'image/png')},headers=auth)
    assert created.status_code==201,created.text
    photo_id=created.json()['id']
    assert client.get(public(photo_id)).status_code==404
    assert client.get(url,headers=auth).json()[0]['approved'] is False
    private=client.get(f'/api/v1/sales/projects/project-1/images/{photo_id}/file',headers=auth)
    assert private.status_code==200 and private.headers['content-type']=='image/jpeg'
    assert client.patch(url+f'/{photo_id}/approval',json={'approved':True}).status_code==401
    approve=client.patch(url+f'/{photo_id}/approval',json={'approved':True},headers=auth)
    assert approve.status_code==200
    got=client.get(public(photo_id))
    assert got.status_code==200 and got.content[:3]==b'\xff\xd8\xff'
    assert client.get('/api/v1/projects/project-1').json()['cover_image_url']==public(photo_id)
    assert client.get('/api/v1/projects/project-2/images/'+photo_id).status_code==404
    client.patch(url+f'/{photo_id}/approval',json={'approved':False},headers=auth)
    assert client.get(public(photo_id)).status_code==404


def test_home_contact_has_no_unapproved_data(client,monkeypatch):
    monkeypatch.delenv('SITEPILOT_PUBLIC_CONTACT_EMAIL',raising=False)
    monkeypatch.delenv('SITEPILOT_PUBLIC_CONTACT_PHONE',raising=False)
    auth=sales_auth(client)
    admin='/api/v1/sales/projects/project-1/salespeople'
    r=client.post(admin,json=contact(),headers=auth)
    assert r.status_code==201
    assert client.get('/api/v1/contact').json()=={'phone':None,'email':None}
    id=r.json()['id']
    client.patch(admin+'/'+id+'/approval',json={'approved':True},headers=auth)
    res=client.get('/api/v1/contact')
    assert res.json()['email']=='nisha@example.com'
    monkeypatch.setenv('SITEPILOT_PUBLIC_CONTACT_EMAIL','office@example.com')
    assert client.get('/api/v1/contact').json()['email']=='office@example.com'
