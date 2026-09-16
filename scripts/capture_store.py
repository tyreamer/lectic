"""Cheap local capture, immutable inputs, personal context and shared source membership.

No retrieval, OCR, transcription, model calls or background jobs. A synced folder
is an input adapter, never the authoritative compiler workspace.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse
import uuid

from ec import (VERSION, Invalid, digest, fingerprint, normalize, read, require, safe_child,
                validate_ir, validate_schema, validate_sources, validate_units, write)
from collection_store import Library

TEXT_EXTENSIONS={'.txt','.md','.vtt','.srt'}


def now(): return datetime.now(timezone.utc).isoformat()


def instant(value):
    try: parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,TypeError) as exc: raise Invalid('Timestamp must be ISO 8601 with a timezone') from exc
    require(parsed.tzinfo is not None,'Timestamp must include a timezone')
    return parsed


def immutable(path,value):
    if path.exists(): require(read(path)==value,'Immutable capture record changed: '+path.name)
    else: write(path,value)


def validate_capture(event):
    validate_schema(event,'capture');instant(event['captured_at'])
    require(event['capture_id'].startswith('capture-'),'Capture ID must start with capture-')
    require(event['original_value'].strip(),'Empty share input')
    url=event.get('url','') or (event['original_value'] if event['source_type']=='url' else '')
    if url:
        parsed=urlparse(url)
        require(parsed.scheme in {'https','http'} and parsed.hostname and not re.search(r'\s',url),'Malformed original URL')
    paths=[]
    for item in event.get('attachments',[]):
        require(Path(item['filename']).name==item['filename'] and item['filename'] not in {'.','..'},'Attachment filename must be a basename')
        require(not Path(item['path']).is_absolute() and '..' not in Path(item['path']).parts,'Unsafe attachment reference')
        paths.append(item['path'])
    require(len(paths)==len(set(paths)),'Duplicate attachment path')
    return event


class CaptureStore:
    def __init__(self,project='.'):
        self.project=Path(project).resolve()
        self.root=self.project/'.expertise-compiler/capture'

    @contextmanager
    def writer(self):
        """OS lock releases on interruption; no stale lock cleanup protocol needed."""
        self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'.writer.lock').open('a+b') as lock:
            if lock.tell()==0: lock.write(b'0');lock.flush()
            lock.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc: raise Invalid('Another capture operation is active; retry after it finishes') from exc
            try: yield
            finally:
                lock.seek(0)
                if os.name=='nt': msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                else: fcntl.flock(lock,fcntl.LOCK_UN)

    def load(self,capture_id):
        event=validate_capture(read(safe_child(self.root/'records',capture_id+'.json')))
        state=read(safe_child(self.root/'state',capture_id+'.json'));validate_schema(state,'capture-state')
        require(event['capture_id']==state['capture_id']==capture_id and state['envelope_hash']==fingerprint(event),'Capture binding mismatch')
        instant(state['imported_at'])
        for item in state['attachment_blobs']:
            blob=self.root/'blobs'/item['blob_hash']
            require(blob.is_file() and digest(blob.read_bytes())==item['blob_hash'],'Capture attachment hash mismatch')
        for aid in state['annotation_ids']:
            note=read(safe_child(self.root/'annotations',aid+'.json'));validate_schema(note,'capture-annotation')
            require(note['capture_id']==capture_id and note['annotation_id']==aid,'Annotation identity mismatch')
        return event,state

    def save_state(self,state):
        validate_schema(state,'capture-state');write(self.root/'state'/f"{state['capture_id']}.json",state)

    def all(self):
        return [self.load(p.stem) for p in sorted((self.root/'state').glob('capture-*.json'))]

    def collection_id(self,name):
        library=Library(self.project)
        for entry in library.index['collections']:
            if name.casefold() in {entry['name'].casefold(),entry['collection_id']}:
                return entry['collection_id']
        require(name.strip(),'Collection name cannot be blank')
        return library.archive(name=name)[1]['collection_id']

    def blob(self,raw):
        h=digest(raw);path=self.root/'blobs'/h
        if path.exists(): require(digest(path.read_bytes())==h,'Canonical blob was modified')
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
                f.write(raw);temp=Path(f.name)
            temp.replace(path)
        return h

    def import_record(self,path):
        path=Path(path).resolve();supplied=read(path)
        require(isinstance(supplied,dict),'Capture input must be a JSON object')
        if path.name.endswith('.capture.json') and 'schema_version' not in supplied:
            from capture_input import expand_input
            event=expand_input(supplied)
        else: event=validate_capture(supplied)
        cid=event['capture_id']
        # Resolve all attachment paths before accepting this envelope; never read outside its folder.
        for attachment in event.get('attachments',[]): safe_child(path.parent,attachment['path'])
        existing=(self.root/'state'/f'{cid}.json').exists()
        record=self.root/'records'/f'{cid}.json'
        immutable(record,event)
        if existing: _,state=self.load(cid)
        else:
            state={'schema_version':VERSION,'capture_id':cid,'envelope_hash':fingerprint(event),'imported_at':now(),
                'collection_ids':list(dict.fromkeys(self.collection_id(name) for name in event.get('requested_collections',[]) or ['Inbox'])),
                'source_ids':[],'attachment_blobs':[],'annotation_ids':[],'capture_status':'captured',
                'processing_status':'pending','issues':[]}
        old={b['path']:b['blob_hash'] for b in state['attachment_blobs']};issues=[]
        for a in event.get('attachments',[]):
            try:
                location=safe_child(path.parent,a['path']);raw=location.read_bytes();h=digest(raw)
                require('sha256' not in a or a['sha256']==h,'Attachment hash differs; sync may be incomplete')
                require('byte_size' not in a or a['byte_size']==len(raw),'Attachment size differs; sync may be incomplete')
                require(a['path'] not in old or old[a['path']]==h,'Previously captured attachment changed')
                old[a['path']]=self.blob(raw)
            except (OSError,Invalid) as exc: issues.append(f"{a['filename']}: {exc}")
        state['attachment_blobs']=[{'path':key,'blob_hash':h} for key,h in sorted(old.items())]
        state['issues']=issues
        prior_status=state['processing_status']
        state['processing_status']='needs_attention' if issues else (
            prior_status if prior_status=='processed' else 'partially_processed' if state['source_ids'] else 'awaiting_retrieval' if self.url(event) else 'pending')
        self.save_state(state)
        return {'capture_id':cid,'new':not existing,'saved':True,'processing_performed':False,'issues':issues}

    def import_folder(self,folder):
        folder=Path(folder).resolve();require(folder.is_dir(),'Synced Inbox folder does not exist')
        report={'phase':'captures_imported','items':[],'annotations':[],'needs_attention':[]}
        paths=sorted(folder.glob('*.json'))
        # Capture records first; annotation events can arrive before their parents and retry next import.
        for annotation in (False,True):
            for path in paths:
                if path.name.endswith('.note.json')!=annotation: continue
                try:
                    require(not path.is_symlink(),'Inbox record must not be a symbolic link')
                    result=self.annotate(read(path)) if annotation else self.import_record(path)
                    report['annotations' if annotation else 'items'].append(result)
                except (OSError,ValueError,KeyError) as exc:
                    report['needs_attention'].append({'file':path.name,'reason':str(exc)})
        return report

    def annotate(self,note):
        validate_schema(note,'capture-annotation');instant(note['annotated_at'])
        require(note['annotation_id'].startswith('annotation-'),'Annotation ID must start with annotation-')
        _,state=self.load(note['capture_id'])
        immutable(self.root/'annotations'/f"{note['annotation_id']}.json",note)
        if note['annotation_id'] in state['annotation_ids']: return {'annotation_id':note['annotation_id'],'new':False}
        state['annotation_ids'].append(note['annotation_id'])
        if note['add_collections']:
            state['collection_ids']=sorted(set(state['collection_ids'])|{self.collection_id(name) for name in note['add_collections']})
        self.save_state(state)
        return {'annotation_id':note['annotation_id'],'new':True}

    @staticmethod
    def url(event):
        value=event.get('url','')
        if not value and re.fullmatch(r'https?://[^\s]+',event['original_value']): value=event['original_value']
        return value

    def notes(self,event,state):
        result=[]
        if event.get('user_note'): result.append({'note':event['user_note'],'recorded_at':event['captured_at'],'origin':'capture'})
        for aid in state['annotation_ids']:
            note=read(self.root/'annotations'/f'{aid}.json')
            if note['user_note']: result.append({'note':note['user_note'],'recorded_at':note['annotated_at'],'origin':aid})
        return result

    def find(self,selector):
        hits=[(event,state) for event,state in self.all() if selector in {event['capture_id'],event.get('title'),event['original_value'],self.url(event)}]
        require(len(hits)==1,'Saved item is missing or ambiguous; list the Inbox and select an item')
        return hits[0]

    def membership(self,selectors,names,mode='add'):
        require(selectors and names,'Choose saved items and collections')
        require(mode in {'add','move','remove'},'Unknown membership operation')
        states=[self.find(selector)[1] for selector in selectors]
        targets={self.collection_id(name) for name in names}
        touched=set()
        for state in states:
            old=set(state['collection_ids']);touched |= old|targets
            updated=targets if mode=='move' else old|targets if mode=='add' else old-targets
            state['collection_ids']=sorted(updated or {self.collection_id('Inbox')})
            self.save_state(state)
        # Membership changes update source snapshots only for already normalized sources.
        for cid in sorted(touched): self.materialize(cid)
        return {'phase':'capture_membership_updated','items':len(states),'mode':mode,'collections':names}

    def status(self,event,state,processed_ids):
        if state['issues']: return 'needs_attention'
        if not state['source_ids']: return 'awaiting_retrieval' if self.url(event) else 'pending'
        unsupported=any(Path(a['filename']).suffix.lower() not in TEXT_EXTENSIONS for a in event.get('attachments',[]))
        if self.url(event) or unsupported: return 'partially_processed'
        return 'processed' if set(state['source_ids'])<=processed_ids else 'partially_processed'

    def processed_sources(self):
        result=set();library=Library(self.project)
        for entry in library.index['collections']:
            folder,data=library.resolve(entry['collection_id'])
            for revision in data['revisions']:
                run=safe_child(folder,revision['run'])
                if (run/'ir.json').exists():
                    ir=validate_ir(run)
                    result.update(row['source_id'] for row in ir['coverage'])
        return result

    def refresh_status(self):
        processed=self.processed_sources()
        for event,state in self.all():
            state['processing_status']=self.status(event,state,processed)
            self.save_state(state)

    def listing(self,collection=None,query=None,since=None,until=None):
        entries=Library(self.project).index['collections'];names={e['collection_id']:e['name'] for e in entries}
        chosen=None
        if collection:
            hits=[e['collection_id'] for e in entries if collection.casefold() in {e['name'].casefold(),e['collection_id']}]
            if not hits: return {'phase':'capture_inbox','items':[]}
            chosen=hits[0]
        start=instant(since) if since else None;end=instant(until) if until else None
        require(not (start and end) or start<end,'Date interval must have since before until')
        processed=self.processed_sources();result=[]
        for event,state in self.all():
            if chosen and chosen not in state['collection_ids']: continue
            captured=instant(event['captured_at'])
            if start and captured<start or end and captured>=end: continue
            notes=self.notes(event,state)
            haystack=' '.join([event['original_value'],event.get('shared_text',''),event.get('title','')]+[n['note'] for n in notes]).casefold()
            if query and not all(word in haystack for word in query.casefold().split()): continue
            result.append({'capture_id':event['capture_id'],'title':event.get('title') or event['original_value'][:100],
                'captured_at':event['captured_at'],'source_type':event['source_type'],'url':self.url(event),
                'collections':[names.get(cid,cid) for cid in state['collection_ids']],
                'capture_status':'captured','processing_status':self.status(event,state,processed),
                'source_ids':state['source_ids'],'user_context':notes,'issues':state['issues'],
                'retrieval':'Captured but linked source content not yet retrieved.' if self.url(event) else 'Only actually supplied content is available.'})
        result.sort(key=lambda r:instant(r['captured_at']),reverse=True)
        return {'phase':'capture_inbox','items':result}

    def canonical_source(self,raw,suffix,event):
        # URL/title are source metadata; annotations, membership and capture time never affect source identity.
        identity=fingerprint({'hash':digest(raw),'suffix':suffix,'url':self.url(event),'title':event.get('title','')})
        filename=identity+suffix;h=digest(raw);sid='src-'+digest((filename+'\0'+h).encode())[:24]
        destination=self.root/'sources'/sid
        if destination.exists(): validate_sources(destination);return sid
        blob=self.root/'blobs'/self.blob(raw)
        doc={'schema_version':VERSION,'source_id':sid,'filename':filename,'title':event.get('title') or None,
             'creator':None,'url':self.url(event) or None,'caption_type':'unknown','content_hash':h,
             'raw_path':f'raw/{sid}{suffix}','segments':normalize(raw,suffix)}
        validate_schema(doc,'source');entry={'source_id':sid,'path':f'sources/{sid}.json','document_hash':fingerprint(doc)}
        destination.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.normalize-',dir=destination.parent) as temp:
            staging=Path(temp)/'run';(staging/'raw').mkdir(parents=True);(staging/'units').mkdir()
            os.link(blob,staging/doc['raw_path'])
            write(staging/entry['path'],doc)
            write(staging/'corpus.json',{'schema_version':VERSION,'corpus_id':'corpus-'+fingerprint([entry]),'sources':[entry]})
            validate_sources(staging);staging.rename(destination)
        return sid

    def normalize_item(self,event,state):
        sources=set(state['source_ids']);issues=[]
        text=event.get('shared_text','')
        if not text and event['source_type']=='text': text=event['original_value']
        if text.strip() and text.strip()!=self.url(event):
            try: sources.add(self.canonical_source(text.encode('utf-8'),'.txt',event))
            except (ValueError,OSError) as exc: issues.append('Shared text: '+str(exc))
        blobs={b['path']:b['blob_hash'] for b in state['attachment_blobs']}
        for a in event.get('attachments',[]):
            suffix=Path(a['filename']).suffix.lower()
            if a['path'] not in blobs:
                issues.append(a['filename']+': attachment not yet available; retry Inbox import after sync.');continue
            if suffix not in TEXT_EXTENSIONS:
                issues.append(a['filename']+': original saved; no content adapter for this file type.');continue
            try: sources.add(self.canonical_source((self.root/'blobs'/blobs[a['path']]).read_bytes(),suffix,event))
            except (ValueError,OSError) as exc: issues.append(a['filename']+': '+str(exc))
        state['source_ids']=sorted(sources);state['issues']=list(dict.fromkeys(state['issues']+issues))
        state['processing_status']=self.status(event,state,set());self.save_state(state)

    def materialize(self,collection_id):
        rows=self.all()
        managed={sid for _,state in rows for sid in state['source_ids']}
        included={sid for _,state in rows if collection_id in state['collection_ids'] for sid in state['source_ids']}
        return Library(self.project).attach_shared(collection_id,[self.root/'sources'/sid for sid in sorted(included)],managed)

    def reuse_checkpoints(self,run):
        """Reuse verified source-local extraction only; cross-source judgments need reconciliation."""
        from workflow import checkpoint_state
        corpus,docs,segments=validate_sources(run);library=Library(self.project)
        _,current,_,_=checkpoint_state(run,corpus,docs,segments)
        occupied={u['unit_id'] for u in current};reused=[]
        historical=[]
        for entry in library.index['collections']:
            folder,data=library.resolve(entry['collection_id'])
            historical.extend(safe_child(folder,r['run']) for r in reversed(data['revisions']))
        for other in historical:
            if other==run or not (other/'ir.json').exists(): continue
            previous_ir=validate_ir(other)
            oc,od,osg=validate_sources(other);parts,_,pending,errors=checkpoint_state(other,oc,od,osg)
            if pending or errors: continue
            receipt=other/'reconciliation.json'
            if not receipt.exists() or read(receipt)!={'schema_version':VERSION,'checkpoint_hash':fingerprint(parts)}: continue
            reviewed={u['unit_id']:u for u in previous_ir['units']}
            for part in parts:
                sid=part['source_id'];target=run/'units'/f'{sid}.json'
                if sid not in docs or docs[sid]!=od[sid] or target.exists(): continue
                units=part['units'];ids={u['unit_id'] for u in units}
                if any(reviewed.get(u['unit_id'])!=u for u in units): continue
                if ids & occupied: continue
                if any(e['source_id']!=sid for u in units for e in u['evidence']): continue
                if any(r['target'] not in ids for u in units for r in u['relations']): continue
                if units: validate_units(units,docs,segments)
                write(target,{**part,'corpus_id':corpus['corpus_id']});occupied |= ids;reused.append(sid)
        return reused

    def process(self,collection):
        from goal_workflow import work
        cid=self.collection_id(collection)
        for event,state in self.all():
            if cid in state['collection_ids']: self.normalize_item(event,state)
        folder,data=self.materialize(cid);run=Library.run(folder,data)
        reused=self.reuse_checkpoints(run)
        result=work(project=self.project,collection=cid,action='prepare')
        return {**result,'capture_context':self.listing(collection)['items'],'reused_capture_sources':reused,
                'capture_note':'Saving and normalization do not prove semantic understanding. Linked pages were not retrieved.'}

    def trace(self,build):
        from goal_workflow import validate_build
        build=Path(build).resolve();validate_build(build)
        manifest=read(build/'manifest.json');folder=build.parent.parent;data=read(folder/'collection.json')
        rev=next(r for r in data['revisions'] if r['revision_id']==manifest['source_revision'])
        ir=validate_ir(safe_child(folder,rev['run']),safe_child(folder,manifest['knowledge_path']))
        result=read(build/'result.json')
        used={uid for key in ('sections','findings','checklist') for section in result.get(key,[]) for uid in section.get('unit_ids',[])}
        source_ids={e['source_id'] for u in ir['units'] if u['unit_id'] in used for e in u['evidence']}
        captures=[{'capture_id':event['capture_id'],'original_value':event['original_value'],'provenance':event['provenance'],
                   'source_ids':sorted(source_ids & set(state['source_ids']))} for event,state in self.all() if source_ids & set(state['source_ids'])]
        return {'phase':'capture_evidence_trace','source_ids':sorted(source_ids),'captures':captures,
                'saved_user_context':read(build/'brief.json')['context'],
                'limits':'Evidence links show cited source influence, not every influence on model reasoning. Personal context is separate from source evidence.'}


def capture_command(*,project='.',action='list',inbox=None,collection=None,items=None,to=None,
                    query=None,since=None,until=None,note=None,build=None):
    store=CaptureStore(project)
    if action=='list': return store.listing(collection,query,since,until)
    if action=='show':
        require(items and len(items)==1,'Select one capture');event,state=store.find(items[0])
        return {'phase':'capture','record':event,'state':state,'user_context':store.notes(event,state)}
    if action=='trace': require(build,'Select a saved build');return store.trace(build)
    with store.writer():
        if action=='import': require(inbox,'Choose a synced Inbox folder');return store.import_folder(inbox)
        if action in {'add','move','remove'}: return store.membership(items,to,action)
        if action=='note':
            require(items and len(items)==1 and note is not None,'Select one saved item and a note')
            event,_=store.find(items[0])
            return store.annotate({'schema_version':VERSION,'annotation_id':'annotation-'+uuid.uuid4().hex,
                'capture_id':event['capture_id'],'annotated_at':now(),'user_note':note,'add_collections':to or []})
        if action=='process': require(collection,'Choose a collection to process');return store.process(collection)
        raise Invalid('Unknown capture action')
