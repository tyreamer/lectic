"""Pilot acceptance boundaries. Run separately from the dependency-free compiler suite."""
import concurrent.futures
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from lectic.cloud.config import Settings, ROOT
from lectic.cloud.db import Database, accounts, captures, packs, results, jobs, shares, backups, uid, SpendingLimit, UncertainCall, YieldJob
from lectic.cloud.api import create_app
from lectic.cloud.runner import execute
from lectic.cloud.retrieval import validate_url, platform, NeedsContent

A, B = "00000000-0000-4000-8000-000000000011", "00000000-0000-4000-8000-000000000012"


def test_busy_account_backlog_does_not_starve_other_account(setup):
    _, db, _ = setup
    for number in range(25): db.enqueue(A, 'backup', {}, 'a-'+str(number))
    other = db.enqueue(B, 'backup', {}, 'b')
    assert db.claim()['owner'] == A
    assert db.claim()['id'] == other['id']


def test_private_storage_secret_key_and_idempotent_duplicate(tmp_path, monkeypatch):
    import httpx
    from lectic.cloud import storage
    settings=Settings(data=tmp_path, dev=False, secret_key='sb_secret_fixture', supabase_url='https://example.supabase.co')
    original=tmp_path/'original'; original.write_bytes(b'original source')
    sent=[]
    def reply(request):
        sent.append(request)
        return httpx.Response(400,json={'statusCode':'409','error':'Duplicate','message':'The resource already exists'})
    client=httpx.Client(transport=httpx.MockTransport(reply))
    monkeypatch.setattr(storage.httpx,'Client',lambda **_:client)
    key=storage.upload_private(settings,A,original)
    assert key.startswith(A+'/originals/')
    assert sent[0].headers['apikey']=='sb_secret_fixture'
    assert 'authorization' not in sent[0].headers
    assert sent[0].content==b'original source'


def test_cancelled_job_survives_worker_loss_without_staying_processing(setup):
    _, db, client = setup
    captured = client.post('/api/v1/captures', json={'kind':'note','text':'Retain this note'},
                           headers={'Idempotency-Key':'cancel-restart'}).json()
    job = db.claim()
    db.mutate(captures, captured['capture_id'], A, state='processing')
    client.post('/api/v1/jobs/'+job['id']+'/cancel')
    db.mutate(jobs, job['id'], A, lease_until=0)
    assert db.claim() is None
    assert db.get(jobs,job['id'],A)['status'] == 'cancelled'
    assert db.get(captures,captured['capture_id'],A)['state'] == 'saved'


@pytest.fixture
def setup(tmp_path):
    settings = Settings(data=tmp_path, database="", dev=True)
    settings.validate()
    db = Database(settings); db.initialize()
    with db.transaction() as c:
        for owner in (A, B): c.execute(accounts.insert().values(id=owner, email=owner+"@example.com"))
    async def auth(request: Request): return request.headers.get("x-test-user", A)
    app = create_app(settings, auth)
    with TestClient(app) as client: yield settings, db, client
    db.engine.dispose()


def run(settings, db, job, monkeypatch):
    monkeypatch.setenv("LECTIC_HOME", str(settings.home(job["owner"])))
    result = execute(settings, db, job)
    db.finish(job, result)
    return result


def test_three_starters_install_and_restart_without_duplicate(setup, monkeypatch):
    settings, db, client = setup
    for starter in client.get('/api/v1/starters').json():
        response = client.post('/api/v1/starters/'+starter['slug']+'/install', headers={'Idempotency-Key':starter['slug']})
        assert response.status_code == 202
        job = db.get(jobs, response.json()['operation_id'])
        first = run(settings, db, job, monkeypatch)
        assert execute(settings, db, job) == first
        assert client.get('/api/v1/packs/'+first['pack_id']+'/download').status_code == 200
    assert len(db.listing(packs, A)) == 3


def test_tenant_boundaries_all_private_endpoints(setup, monkeypatch):
    settings, db, client = setup
    job = db.enqueue(A, 'install_starter', {'slug':'debugging-starter'}, 'starter')
    pack_id = run(settings, db, job, monkeypatch)['pack_id']
    capture = client.post('/api/v1/captures', json={'kind':'note','title':'private','text':'Secret notes'}, headers={'Idempotency-Key':'capture'}).json()
    result_id = uid()
    with db.transaction() as c: c.execute(results.insert().values(id=result_id, owner=A, title='private', data={'markdown':'secret'}))
    share_job = db.enqueue(A,'share',{'pack_id':pack_id},'share')
    shared = run(settings, db, share_job, monkeypatch)
    headers={'x-test-user':B,'Idempotency-Key':'attack'}
    for path in [f'/captures/{capture["capture_id"]}',f'/captures/{capture["capture_id"]}/original',
                 f'/packs/{pack_id}',f'/packs/{pack_id}/download',f'/results/{result_id}',f'/results/{result_id}/download',
                 f'/jobs/{job["id"]}']:
        assert client.get('/api/v1'+path,headers=headers).status_code==404, path
    mutations=[(f'/jobs/{job["id"]}/cancel',{}),(f'/packs/{pack_id}/shares',{}),
               (f'/shares/{shared["share_id"]}/revoke',{}),('/creations',{'pack_id':pack_id,'format':'Plan','brief':'private work'}),
               ('/packs',{'title':'attack','source_ids':[capture['capture_id']]}),
               (f'/packs/import/{capture["capture_id"]}',{}),('/captures',{'kind':'note','text':'attack','parent_id':capture['capture_id']})]
    for path, body in mutations:
        assert client.post('/api/v1'+path,json=body,headers=headers).status_code==404, path
    assert client.put('/api/v1/captures/'+capture['capture_id']+'/content',content=b'bad',headers=headers).status_code==404
    library=client.get('/api/v1/library',headers=headers).json()
    assert all(not library[k] for k in ('sources','packs','results','operations'))
    assert client.get('/api/v1/shares',headers=headers).json()==[]
    assert client.post('/api/v1/captures',json={'kind':'note','text':'x','owner':A},headers=headers).status_code==422
    assert client.post('/api/v1/captures',json={'kind':'note','text':'x','path':'../../x'},headers=headers).status_code==422


def test_upload_interruption_idempotency_and_quota(setup):
    settings, db, client = setup
    payload={'kind':'upload','filename':'note.txt','title':'note','size':5}
    first=client.post('/api/v1/captures',json=payload,headers={'Idempotency-Key':'upload'}).json()
    assert client.post('/api/v1/captures',json=payload,headers={'Idempotency-Key':'upload'}).json()==first
    assert db.get(accounts,A)['used_bytes']==5
    assert client.post('/api/v1/captures',json={**payload,'size':6},headers={'Idempotency-Key':'upload'}).status_code==409
    endpoint='/api/v1/captures/'+first['capture_id']+'/content'
    assert client.put(endpoint,content=b'abc').status_code==400
    assert db.get(jobs,first['operation_id'])['status']=='awaiting_upload'
    assert client.get('/api/v1/library').json()['sources'][0]['needs_upload'] is True
    assert client.put(endpoint,content=b'hello').status_code==202
    assert client.get('/api/v1/library').json()['sources'][0]['needs_upload'] is False
    assert client.put(endpoint,content=b'hello').status_code==202
    assert client.put(endpoint,content=b'other').status_code==409
    assert client.put(endpoint,content=b'too large').status_code==413


def test_sharing_fixed_copy_and_revocation(setup, monkeypatch):
    settings, db, client = setup
    pack_job=db.enqueue(A,'install_starter',{'slug':'debugging-starter'},'starter')
    pack_id=run(settings,db,pack_job,monkeypatch)['pack_id']
    share_job=db.enqueue(A,'share',{'pack_id':pack_id},'share')
    shared=run(settings,db,share_job,monkeypatch)
    token=shared['url'].rsplit('/',1)[1]
    preview=client.get('/api/v1/shared/'+token).json()
    assert set(preview)=={'title','preview','source_count'}
    copied=client.post('/api/v1/shared/'+token+'/copy',headers={'x-test-user':B,'Idempotency-Key':'copy'}).json()
    copied_id=run(settings,db,db.get(jobs,copied['operation_id']),monkeypatch)['pack_id']
    assert db.get(packs,copied_id,B)
    assert client.post('/api/v1/shares/'+shared['share_id']+'/revoke',headers={'Idempotency-Key':'revoke'}).status_code==202
    assert client.get('/api/v1/shared/'+token).status_code==404
    assert client.post('/api/v1/shared/'+token+'/copy',headers={'x-test-user':B,'Idempotency-Key':'another'}).status_code==404
    assert client.get('/api/v1/packs/'+copied_id+'/download',headers={'x-test-user':B}).status_code==200


def test_atomic_spending_and_paid_call_cache(setup):
    settings, db, _=setup
    db.settings=replace(settings,monthly_microdollars=100)
    def reserve(i):
        try: db.reserve(A,str(i),40); return True
        except SpendingLimit: return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: accepted=list(pool.map(reserve,range(8)))
    assert sum(accepted)==2
    existing=str(accepted.index(True))
    with pytest.raises(UncertainCall): db.reserve(A,existing,40)
    db.settle(A,existing,10,{'value':'done'})
    assert db.reserve(A,existing,40)=={'value':'done'}
    db.reserve(B,'new',40)


def test_priority_home_serialization_and_expired_lease(setup):
    settings, db, _=setup
    background=db.enqueue(A,'capture',{},'background',8)
    foreground=db.enqueue(A,'create',{},'foreground',0)
    other=db.enqueue(B,'capture',{},'other',8)
    first=db.claim(); assert first['id']==foreground['id']
    second=db.claim(); assert second['id']==other['id']
    assert db.claim() is None
    db.finish(first,{'result_id':'done'})
    assert db.claim()['id']==background['id']


@pytest.mark.parametrize('url',['http://localhost/a','http://127.0.0.1/a','http://169.254.169.254/','file:///etc/passwd','https://x.com:8080/post','https://user:pass@example.com/','http://[::1]/'])
def test_private_retrieval_blocked(url):
    with pytest.raises(ValueError): validate_url(url,resolve=False)


def test_excluded_social_shapes():
    for url in ('https://instagram.com/stories/name/1','https://instagram.com/direct/inbox','https://x.com/user'):
        with pytest.raises(NeedsContent): platform(url)


def test_production_fails_closed(tmp_path):
    with pytest.raises(ValueError): create_app(Settings(data=tmp_path,dev=False,database='',supabase_url='',publishable_key='',secret_key=''))
    with pytest.raises(ValueError): create_app(Settings(data=tmp_path,dev=True,origin='https://example.com'))


def test_backup_restores_collection_into_fresh_home(setup,monkeypatch,tmp_path):
    settings, db, client=setup
    job=db.enqueue(A,'install_starter',{'slug':'startup-principles'},'starter')
    run(settings,db,job,monkeypatch)
    from home_archive import archive_home, restore
    from collection_store import Library
    from verify import verify_collection
    raw=archive_home(settings.home(A))
    archive=tmp_path/'backup.lectic-home';archive.write_bytes(raw)
    restored=tmp_path/'restored';monkeypatch.setenv('LECTIC_HOME',str(restored))
    restore(tmp_path,str(archive))
    catalog=Library(tmp_path).catalog()
    assert len(catalog)==1
    assert verify_collection(tmp_path,catalog[0]['collection_id'])['overall']=='verified'


def test_derivations_roundtrip_and_automatic_transcripts(setup,monkeypatch,tmp_path):
    settings,db,client=setup
    monkeypatch.setenv('LECTIC_HOME',str(settings.home(A)))
    from ec import ingest,write,validate_sources,read
    from collection_store import Library
    from goal_workflow import work
    from packs import build_pack,install_pack,open_pack
    sources=tmp_path/'input';sources.mkdir()
    transcript='WEBVTT\n\n00:00.000 --> 00:03.000\nTest the original reproducer before changing code.\n'
    (sources/'automatic.vtt').write_text(transcript)
    metadata=tmp_path/'meta.json';write(metadata,{'automatic.vtt':{'title':'Automatic transcript','creator':'Automatic processing','caption_type':'automatic'}})
    source_run=tmp_path/'source-run';ingest(sources,source_run,metadata)
    corpus,docs,_=validate_sources(source_run);sid,doc=next(iter(docs.items()));segment=doc['segments'][0]
    unit={'schema_version':'1.0','unit_id':'automatic-test','type':'procedure','status':'explicit','title':'Test before changing','statement':segment['text'],'scope':'Automatic transcript; unverified','derivation':'',
          'evidence':[{'source_id':sid,'segment_id':segment['segment_id'],'quote':segment['text']}],'attribution':[],'relations':[]}
    write(source_run/'units'/(sid+'.json'),{'schema_version':'1.0','corpus_id':corpus['corpus_id'],'source_id':sid,'note':'Automatic transcript','units':[unit]})
    record={'schema_version':'1.0','records':[{'filename':'automatic.vtt','kind':'transcript','original_sha256':'a'*64,'reference':{'start':0,'end':3},'model':'whisper-1','processing_version':'pilot-1'}]}
    write(source_run/'derivations.json',record)
    Library(tmp_path).archive(adopt=source_run,name='Automatic media')
    work(project=tmp_path,collection='Automatic media',action='prepare',reconciled=True)
    pack=tmp_path/'automatic.lectic';build_pack(tmp_path,'Automatic media',pack,include_sources=True)
    manifest,members=open_pack(pack.read_bytes());assert manifest['sources'][0]['caption_type']=='automatic';assert 'sources/derivations.json' in members
    monkeypatch.setenv('LECTIC_HOME',str(settings.home(B)))
    installed=install_pack(tmp_path,str(pack));assert installed['verification']=='verified'
    library=Library(tmp_path);folder,data=library.resolve(installed['collection_id'])
    assert read(library.run(folder,data)/'derivations.json')==record


def test_background_yields_at_paid_boundary_for_creation(setup):
    settings,db,_=setup
    background=db.enqueue(A,'capture',{},'media',5)
    claimed=db.claim();assert claimed['id']==background['id']
    foreground=db.enqueue(A,'create',{},'create',0)
    with pytest.raises(YieldJob):db.prioritize_creation(A,background['id'])
    db.yield_job(claimed)
    assert db.get(jobs,background['id'])['attempts']==0
    assert db.claim()['id']==foreground['id']


def test_backup_endpoints_and_retention_are_owned(setup,monkeypatch):
    settings,db,client=setup
    from lectic.cloud import runner
    removed=[]
    monkeypatch.setattr(runner,'upload_private',lambda *_:A+'/backups/'+'a'*64)
    monkeypatch.setattr(runner,'remove_private_backup',lambda *args:removed.append(args[-1]))
    run(settings,db,db.enqueue(A,'install_starter',{'slug':'debugging-starter'},'starter'),monkeypatch)
    for i in range(8):run(settings,db,db.enqueue(A,'backup',{},'backup-'+str(i)),monkeypatch)
    kept=db.listing(backups,A);assert len(kept)==7
    assert not removed  # Identical snapshots still referenced by retained backups remain in cloud storage.
    backup_id=kept[0]['id']
    assert client.get('/api/v1/backups/'+backup_id+'/download').status_code==200
    assert client.get('/api/v1/backups',headers={'x-test-user':B}).json()==[]
    assert client.get('/api/v1/backups/'+backup_id+'/download',headers={'x-test-user':B}).status_code==404
    assert client.post('/api/v1/backups/'+backup_id+'/restore',headers={'x-test-user':B,'Idempotency-Key':'restore'}).status_code==404
