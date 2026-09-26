"""Hosted chat contract tests: real routes/compiler, isolated homes, mocked providers.

These do not certify a deployed Supabase OAuth flow or a real chat client's UI.
"""
import base64
from dataclasses import replace
import json
import time
from uuid import uuid4
import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from lectic.cloud import auth, models
from lectic.cloud.api import create_app
from lectic.cloud.config import Settings
from lectic.cloud.db import Database, accounts, invites, captures, jobs, packs, results, shares
from lectic.cloud.tests.test_pilot import A, B, run


def jwt(claims):
    # Only the mocked auth server accepts these tokens. The production verifier
    # must get a successful /user response before reading any payload claims.
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "fixture." + encoded + ".fixture-signature"


@pytest.fixture
def chat(tmp_path, monkeypatch):
    settings = Settings(data=tmp_path, database="", dev=True, chat_enabled=True,
                        supabase_url="https://auth.example.test", publishable_key="fixture")
    db = Database(settings); db.initialize()
    with db.transaction() as c:
        for owner in (A, B):
            c.execute(accounts.insert().values(id=owner, email=owner+"@example.test"))
            c.execute(invites.insert().values(id=owner+"@example.test", enabled=1))
    valid, active, tokens = {}, set(), {}
    def issue(owner=A, **changes):
        claims = dict(sub=owner, iss=settings.supabase_url+"/auth/v1", aud=settings.mcp_resource,
                      exp=time.time()+3600, client_id=str(uuid4()), session_id=str(uuid4()))
        claims.update(changes)
        token = jwt(claims)
        valid[token] = {"id": owner, "email": owner+"@example.test", "email_confirmed_at": "2026-01-01"}
        active.add((claims["session_id"], owner))
        return token, claims
    for owner in (A, B): tokens[owner] = issue(owner)[0]
    def reply(request):
        assert str(request.url) == settings.supabase_url+"/auth/v1/user"
        value=valid.get(request.headers.get("authorization", "").removeprefix("Bearer "))
        return httpx.Response(200 if value else 401, json=value or {})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(auth.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(reply), **kw))
    monkeypatch.setattr(auth, "live_session", lambda db, session, owner: (session,owner) in active)
    app=create_app(settings)
    # Browser endpoints in this fixture use their own explicit test identity;
    # the MCP endpoint still goes through the real OAuth claim/invite checks.
    async def browser(request: Request): return request.headers.get("x-test-user", A)
    app.dependency_overrides[auth.identity]=browser
    with TestClient(app) as client:
        yield settings,db,client,tokens,issue,active,valid
    db.engine.dispose()


def rpc(chat, method="tools/list", params=None, owner=A, token=None, **kwargs):
    return chat[2].post("/mcp", json={"jsonrpc":"2.0","id":1,"method":method,"params":params or {}},
                        headers={"Authorization":"Bearer "+(token if token is not None else chat[3][owner]), **kwargs})


def call(chat, name, args=None, owner=A):
    response=rpc(chat,"tools/call",{"name":name,"arguments":args or {}},owner)
    assert response.status_code==200, response.text
    value=response.json()
    assert "error" not in value, value
    assert not value["result"].get("isError"), value
    return value["result"]["structuredContent"]


def test_discovery_requires_oauth_even_on_loopback_and_creates_nothing(chat):
    settings,db,client,*_=chat
    metadata=client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["resource"]==settings.mcp_resource
    assert metadata["authorization_servers"]==[settings.supabase_url+"/auth/v1"]
    response=client.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"initialize"})
    assert response.status_code==401 and 'resource_metadata=' in response.headers['www-authenticate']
    assert client.get('/mcp').status_code==401
    for owner in (A,B):
        data=call(chat,"lectic_library",owner=owner)
        assert all(data[k]==[] for k in ("sources","packs","results","operations"))
    init=rpc(chat,"initialize",{"protocolVersion":"2025-11-25"}).json()["result"]
    assert init["serverInfo"]["name"]=="lectic-personal"
    assert "Quick save" in init["instructions"] and "private context" in init["instructions"]
    tools=rpc(chat).json()["result"]["tools"]
    assert next(t for t in tools if t['name']=='lectic_read')['annotations']['readOnlyHint']
    assert not db.listing(jobs,A)


@pytest.mark.parametrize("change", [
    {"aud":"authenticated"}, {"aud":"https://other.test/mcp"}, {"iss":"https://other.test/auth/v1"},
    {"exp":0}, {"client_id":None}, {"client_id":"not-an-id"}, {"session_id":"broken"}, {"sub":B},
])
def test_wrong_audience_issuer_expiry_client_session_or_subject_is_rejected(chat,change):
    token,_=chat[4](**change)
    assert rpc(chat,token=token).status_code==401


def test_forged_payload_revoked_session_and_revoked_invite_fail_closed(chat):
    token,claims=chat[4]()
    assert rpc(chat,token=token+"forged").status_code==401
    assert rpc(chat,token=token).status_code==200
    chat[5].remove((claims['session_id'],A))
    assert rpc(chat,token=token).status_code==401
    with chat[1].transaction() as c:
        c.execute(invites.update().where(invites.c.id==A+'@example.test').values(enabled=0))
    assert rpc(chat).status_code==403


def test_provider_outage_does_not_force_reauthorization(chat,monkeypatch):
    class Unavailable:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,*args,**kwargs): raise httpx.ConnectError('Provider unavailable')
    monkeypatch.setattr(auth.httpx,'AsyncClient',lambda **kwargs:Unavailable())
    response=rpc(chat)
    assert response.status_code==503
    assert 'www-authenticate' not in response.headers
    assert not chat[1].listing(jobs,A)


def test_oauth_token_cannot_be_used_for_browser_api(chat):
    chat[2].app.dependency_overrides.clear()
    chat[2].app.state.settings=replace(chat[0],dev=False)
    assert chat[2].get('/api/v1/library',headers={'Authorization':'Bearer '+chat[3][A]}).status_code==401
    browser_token,_=chat[4](aud='authenticated',client_id=None)
    assert chat[2].get('/api/v1/library',headers={'Authorization':'Bearer '+browser_token}).status_code==200
    assert rpc(chat,token=browser_token).status_code==401


def test_save_is_immediate_deferred_and_idempotent_then_processing_is_explicit(chat):
    args=dict(request_id=str(uuid4()),kind='note',title='My research',text='Listen before proposing a solution.')
    saved=call(chat,'lectic_capture_save',args)
    assert call(chat,'lectic_capture_save',args)==saved
    db=chat[1]
    assert len(db.listing(captures,A))==1 and db.claim() is None
    assert db.get(jobs,saved['operation_id'])['status']=='deferred'
    bad=rpc(chat,'tools/call',{'name':'lectic_capture_save','arguments':{**args,'text':'Changed'}}).json()
    assert bad['result']['isError']
    op=call(chat,'lectic_process_source',{'source_id':saved['capture_id']})
    assert op['operation_id']==saved['operation_id']
    assert db.claim()['id']==op['operation_id']
    assert call(chat,'lectic_process_source',{'source_id':saved['capture_id']})==op


def test_tenant_ids_are_never_client_controlled(chat):
    args=dict(request_id=str(uuid4()),kind='note',title='Private',text='Private source')
    saved=call(chat,'lectic_capture_save',args)
    attacks=[('lectic_read',{'kind':'source','id':saved['capture_id']}),
             ('lectic_process_source',{'source_id':saved['capture_id']}),
             ('lectic_operation',{'operation_id':saved['operation_id'],'action':'cancel'}),
             ('lectic_build_pack',{'request_id':str(uuid4()),'title':'Stolen','source_ids':[saved['capture_id']]}),
             ('lectic_capture_save',{**args,'request_id':str(uuid4()),'parent_id':saved['capture_id']})]
    for name,arguments in attacks:
        result=rpc(chat,'tools/call',{'name':name,'arguments':arguments},B).json()['result']
        assert result['isError'] and 'Private source' not in json.dumps(result)
    for field in ('owner','tenant','path','LECTIC_HOME'):
        value=rpc(chat,'tools/call',{'name':'lectic_capture_save','arguments':{**args,field:B}}).json()
        assert value['error']['code']==-32602
    assert call(chat,'lectic_library',owner=B)['sources']==[]


def test_transport_rejects_origin_batch_unknown_tools_and_notifications_cannot_mutate(chat):
    assert rpc(chat,Origin='https://evil.example').status_code==403
    assert rpc(chat,**{'MCP-Protocol-Version':'broken'}).status_code==400
    client=chat[2]; headers={'Authorization':'Bearer '+chat[3][A]}
    assert client.post('/mcp',json=[],headers=headers).status_code==400
    notification={'jsonrpc':'2.0','method':'tools/call','params':{'name':'lectic_capture_save','arguments':{'kind':'note','title':'x','text':'x','request_id':str(uuid4())}}}
    assert client.post('/mcp',json=notification,headers=headers).status_code==400
    notification['method']='notifications/initialized'
    assert client.post('/mcp',json=notification,headers=headers).status_code==202
    assert not chat[1].listing(captures,A)
    assert rpc(chat,'tools/call',{'name':'../../admin'}).json()['error']['code']==-32602
    assert client.get('/mcp',headers=headers).status_code==405
    assert client.get('/mcp',headers={**headers,'Origin':'https://evil.example'}).status_code==403
    response=client.post('/mcp',content=b'{',headers={**headers,'Content-Type':'application/json'})
    assert response.status_code==400 and response.json()['error']['code']==-32700


class FixtureModel:
    """Deterministic provider responses; real compiler validation is still exercised."""
    last_model='fixture-not-a-real-model'
    def __init__(self): self.extractions=0
    def json(self,purpose,payload,schema):
        if 'source' in payload:
            self.extractions+=1
            doc=payload['source']; segment=doc['segments'][0]
            return {'units':[{'schema_version':'1.0','unit_id':payload['prefix']+'-practice','type':'procedure','status':'explicit',
                'title':'Interview practice','statement':segment['text'],'scope':'Provided notes','derivation':'',
                'evidence':[{'source_id':doc['source_id'],'segment_id':segment['segment_id'],'quote':segment['text']}],
                'attribution':[],'relations':[]}]}
        if 'relations' in schema['properties']: return {'relations':[],'note':'Distinct practices.'}
        if 'accepted' in schema['properties']: return {'accepted':True,'issues':[]}
        ids=[u['unit_id'] for u in payload['knowledge']['units']]
        text=payload['brief']['objective']+'\n1. Ask about a recent experience.\n2. Listen before proposing a solution.'
        method={'schema_version':'1.0','capability_id':'prepare-interviews','title':'Prepare interviews','description':'Apply interview practices.',
            'rationale':'Use source evidence.','inputs':'An interview goal','output_contract':'Practical steps',
            'unit_ids':ids,'steps':[{'instruction':'Prepare and listen.','unit_ids':ids}],
            'boundaries':['Notes do not prove customer demand.'],'conflict_policy':'Keep disagreements visible.',
            'checks':['Check quotations.'],'examples':[{'input':'A hypothetical interview','output':'Ask about a recent experience.','unit_ids':ids,'status':'synthetic'}]}
        return {'method':method,'coverage_reason':'The supplied notes support interview preparation.','unsupported':[],
            'outcome':{'schema_version':'1.1','target':payload['target'],'summary':text,
                'sections':[{'kind':'steps','title':'Your next interview','content':text,'unit_ids':ids,'status':'synthesized'}],
                'disagreements':[],'limitations':['Teaching fixture; not effectiveness evidence.'],'unsupported':[],'additional_general_advice':[]}}


def test_chat_sources_to_pack_two_results_and_revocable_recipient_copy(chat,monkeypatch):
    settings,db,client,*_=chat
    model=FixtureModel()
    monkeypatch.setattr(models,'Model',lambda *args:model)
    source_ids=[]
    for note in ['Ask about a recent experience instead of a hypothetical preference.','Listen before proposing a solution to the customer.']:
        saved=call(chat,'lectic_capture_save',{'request_id':str(uuid4()),'title':'My interview notes','kind':'note','text':note,'process':True})
        run(settings,db,db.get(jobs,saved['operation_id']),monkeypatch)
        source_ids.append(saved['capture_id'])
    args={'request_id':str(uuid4()),'title':'My customer interviews','source_ids':source_ids}
    operation=call(chat,'lectic_build_pack',args)
    assert call(chat,'lectic_build_pack',args)==operation
    pack_id=run(settings,db,db.get(jobs,operation['operation_id']),monkeypatch)['pack_id']
    status=call(chat,'lectic_operation',{'operation_id':operation['operation_id']})
    assert status['status']=='complete' and status['result']['pack_id']==pack_id
    context=call(chat,'lectic_read',{'kind':'pack','id':pack_id})
    assert 'Source:' in context['content'] and 'Ask about a recent experience' in context['content']
    assert model.extractions==2
    first_page=call(chat,'lectic_read',{'kind':'pack','id':pack_id,'limit':1000})
    second_page=call(chat,'lectic_read',{'kind':'pack','id':pack_id,'offset':1000})
    assert first_page['next_offset']==1000
    assert first_page['content']+second_page['content']==context['content']
    for format,brief in [('Plan','Prepare my first customer interview'),('Checklist','Check my upcoming customer interview')]:
        op=call(chat,'lectic_create',{'request_id':str(uuid4()),'pack_id':pack_id,'format':format,'brief':brief})
        created=run(settings,db,db.get(jobs,op['operation_id']),monkeypatch)['result_id']
        result=json.loads(call(chat,'lectic_read',{'kind':'result','id':created})['content'])
        assert brief in result['markdown'] and result['references']
        for ref in result['references']:
            assert ref['quote'] in ref['passage']
            # Resolve the quoted passage from the actual packed document.
            assert ref['source_id'] in context['content']
            proof=call(chat,'lectic_evidence',{'pack_id':pack_id,'source_id':ref['source_id'],'segment_id':ref['segment_id']})
            assert ref['quote'] in proof['segment']['text']
            assert rpc(chat,'tools/call',{'name':'lectic_evidence','arguments':{'pack_id':pack_id,'source_id':ref['source_id'],'segment_id':ref['segment_id']}},B).json()['result']['isError']
        assert rpc(chat,'tools/call',{'name':'lectic_read','arguments':{'kind':'result','id':created}},B).json()['result']['isError']
    assert len(db.listing(results,A))==2 and model.extractions==2
    for name,args in [('lectic_read',{'kind':'pack','id':pack_id}),('lectic_create',{'request_id':str(uuid4()),'pack_id':pack_id,'brief':'Steal this pack'}),('lectic_share_pack',{'request_id':str(uuid4()),'pack_id':pack_id})]:
        assert rpc(chat,'tools/call',{'name':name,'arguments':args},B).json()['result']['isError']
    op=call(chat,'lectic_share_pack',{'request_id':str(uuid4()),'pack_id':pack_id})
    shared=run(settings,db,db.get(jobs,op['operation_id']),monkeypatch)
    token=shared['url'].rsplit('/',1)[1]
    op=call(chat,'lectic_copy_shared_pack',{'request_id':str(uuid4()),'share_token':token},B)
    copied=run(settings,db,db.get(jobs,op['operation_id']),monkeypatch)['pack_id']
    assert call(chat,'lectic_read',{'kind':'pack','id':copied},B)['title']=='My customer interviews'
    assert rpc(chat,'tools/call',{'name':'lectic_revoke_share','arguments':{'request_id':str(uuid4()),'share_id':shared['share_id']}},B).json()['result']['isError']
    call(chat,'lectic_revoke_share',{'request_id':str(uuid4()),'share_id':shared['share_id']})
    assert client.get('/api/v1/shared/'+token).status_code==404
    assert call(chat,'lectic_read',{'kind':'pack','id':copied},B)['state']=='ready'


def test_blocked_retrieval_reports_needs_content_instead_of_ready(chat,monkeypatch):
    from lectic.cloud import retrieval
    def blocked(*args): raise retrieval.NeedsContent('The complete post was unavailable. Add screenshots or video.')
    monkeypatch.setattr(retrieval,'retrieve',blocked)
    saved=call(chat,'lectic_capture_save',{'request_id':str(uuid4()),'kind':'url','title':'A blocked post','url':'https://example.com/post','process':True})
    run(chat[0],chat[1],chat[1].get(jobs,saved['operation_id']),monkeypatch)
    operation=call(chat,'lectic_operation',{'operation_id':saved['operation_id']})
    assert operation['status']=='complete' and operation['source']['state']=='needs_content'
    assert 'Add screenshots' in operation['source']['reason']
    assert 'https://example.com/post' in call(chat,'lectic_read',{'kind':'source','id':saved['capture_id']})['content']


def test_disabled_local_preview_advertises_no_public_connection(tmp_path):
    with TestClient(create_app(Settings(data=tmp_path,dev=True,chat_enabled=False))) as client:
        config=client.get('/api/v1/config').json()
        assert config['chatEnabled'] is False and config['mcpUrl'] is None
        assert client.get('/.well-known/oauth-protected-resource/mcp').status_code==503
        assert client.post('/mcp',json={}).status_code==503
