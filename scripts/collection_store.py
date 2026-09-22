"""Private local collections layered on immutable source snapshots and IR history."""
from pathlib import Path
import os
import shutil
import tempfile
import uuid
from ec import VERSION, Invalid, digest, fingerprint, ingest, read, require, safe_child, validate_schema, validate_sources, validate_ir, validate_units, write
from ingestors import adapter_for
from home import storage_root


class Library:
    def __init__(self, project, home=None):
        self.project = Path(project).resolve()
        self.root = Path(home).resolve() if home else storage_root(self.project)
        self.path = self.root / 'library.json'
        self.index = read(self.path) if self.path.exists() else {'schema_version':VERSION,'collections':[], 'active_collection':None}
        require(type(self.index) is dict and self.index.get('schema_version') == VERSION and type(self.index.get('collections')) is list, 'Malformed collection library')
        seen_ids, seen_names = set(), set()
        for entry in self.index['collections']:
            require(type(entry) is dict and set(entry) == {'collection_id','name','path'} and
                    all(type(v) is str and v.strip() for v in entry.values()), 'Malformed collection entry')
            require(entry['collection_id'] not in seen_ids and entry['name'].casefold() not in seen_names, 'Duplicate collection identity')
            safe_child(self.root,entry['path'])
            seen_ids.add(entry['collection_id']); seen_names.add(entry['name'].casefold())
        require(self.index.get('active_collection') is None or self.index['active_collection'] in seen_ids, 'Unknown active collection')

    def resolve(self, selector=None):
        selector = selector or self.index.get('active_collection')
        if not selector: return None
        hits = [c for c in self.index['collections'] if selector.casefold() in {c['name'].casefold(),c['collection_id'].casefold()}]
        require(len(hits) == 1, 'Collection name is missing or ambiguous')
        folder = safe_child(self.root, hits[0]['path'])
        data = read(folder / 'collection.json'); validate_schema(data, 'collection')
        require(data['collection_id'] == hits[0]['collection_id'], 'Collection identity mismatch')
        revisions = [r['revision_id'] for r in data['revisions']]
        require(len(revisions) == len(set(revisions)) and data['active_revision'] in revisions, 'Malformed source revisions')
        if 'revision_history' in data:
            require(set(data['revision_history'])<=set(revisions) and data['revision_history'][-1]==data['active_revision'], 'Malformed revision history')
        return folder, data

    def save(self, folder, data):
        validate_schema(data, 'collection')
        write(folder / 'collection.json', data)
        entry = {'collection_id':data['collection_id'],'name':data['name'],'path':folder.relative_to(self.root).as_posix()}
        self.index['collections'] = [c for c in self.index['collections'] if c['collection_id'] != data['collection_id']] + [entry]
        self.index['active_collection'] = data['collection_id']
        write(self.path, self.index)

    def archive(self, input=None, *, name=None, collection=None, metadata=None, adopt=None, add=False, remove=None, replace=False):
        existing = self.resolve(collection) if collection else None
        if existing:
            folder, data = existing
            require(add or remove or replace or adopt is not None, 'Adding material to an existing collection needs the add action')
        else:
            name = name or (Path(input or adopt).name.replace('-', ' ').replace('_', ' ').title() + ' Sources')
            require(not any(c['name'].casefold() == name.casefold() for c in self.index['collections']), 'That collection name already exists; use add or select it')
            cid = 'collection-' + uuid.uuid4().hex[:16]
            folder = self.root / 'collections' / cid
            data = {'schema_version':VERSION,'collection_id':cid,'name':name,'active_revision':'pending','revisions':[],'briefs':[],'builds':[]}
        folder.mkdir(parents=True, exist_ok=True)
        previous = self.run(folder, data) if data['revisions'] else None
        with tempfile.TemporaryDirectory(prefix='.archive-', dir=folder) as temporary:
            temp = Path(temporary)
            if adopt:
                original = Path(adopt).resolve()
                validate_sources(original)
                require(not any(p.is_symlink() for p in original.rglob('*')), 'Cannot adopt symlinked run content')
                candidate = temp / 'run'
                shutil.copytree(original, candidate)
            else:
                records = {}
                if previous:
                    _, docs, _ = validate_sources(previous)
                    for doc in docs.values():
                        records[doc['filename']] = ((previous / doc['raw_path']).read_bytes(),
                                                   {k:doc[k] for k in ('title','creator','url','caption_type')})
                if remove:
                    require(previous is not None, 'Source removal needs an existing collection')
                    for selector in remove:
                        matches=[d for d in docs.values() if selector in {d['source_id'],d['filename'],d['title']}]
                        require(len(matches)==1,'Source name is missing or ambiguous: '+selector)
                        records.pop(matches[0]['filename'],None)
                for record in (adapter_for(input).collect(metadata) if input else []):
                    filename = record.filename
                    if filename in records and not replace:
                        if records[filename][0] == record.raw: continue
                        filename = '_imports/' + digest(record.raw)[:16] + '/' + filename
                    records[filename] = (record.raw, record.metadata)
                inputs = temp / 'inputs'; inputs.mkdir()
                meta = {}
                for filename, (raw, m) in records.items():
                    target = safe_child(inputs, filename); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
                    meta[filename] = m
                write(temp / 'metadata.json', meta)
                candidate = temp / 'run'
                if records:
                    ingest(inputs, candidate, temp / 'metadata.json')
                    if previous:
                        # Retain shared storage for unchanged sources during legacy additions too.
                        _,new_docs,_=validate_sources(candidate)
                        for sid,doc in new_docs.items():
                            if sid not in docs or docs[sid]!=doc: continue
                            for relative in (f'sources/{sid}.json',doc['raw_path']):
                                target=safe_child(candidate,relative)
                                linked=target.with_name(target.name+'.link')
                                try:
                                    os.link(safe_child(previous,relative),linked)
                                    os.replace(linked,target)
                                except OSError:
                                    # Legacy ingestion also supports filesystems without links.
                                    if linked.exists(): linked.unlink()
                else:
                    write(candidate / 'corpus.json', {'schema_version':VERSION,'sources':[], 'corpus_id':'corpus-'+fingerprint([])})
                    (candidate / 'units').mkdir()
            corpus, docs, _ = validate_sources(candidate)
            revision_id = 'source-' + corpus['corpus_id'].split('-')[1][:24]
            destination = folder / 'sources' / revision_id
            if destination.exists():
                require(validate_sources(destination)[0] == corpus, 'Source revision identity collision')
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if previous and not adopt:
                    self.carry_checkpoints(previous,candidate)
                candidate.rename(destination)
            history=data.get('revision_history',[r['revision_id'] for r in data['revisions']])
            if not history or history[-1]!=revision_id: history.append(revision_id)
            data['revision_history']=history
            if revision_id not in {r['revision_id'] for r in data['revisions']}:
                data['revisions'].append({'revision_id':revision_id,'corpus_id':corpus['corpus_id'],'run':destination.relative_to(folder).as_posix()})
            data['active_revision'] = revision_id
            self.save(folder, data)
        return folder, data

    @staticmethod
    def carry_checkpoints(previous,candidate):
        """Invalidate evidence/dependency closure when a source disappears or changes."""
        corpus,docs,segments=validate_sources(candidate)
        parts=[read(p) for p in (previous/'units').glob('*.json')]
        valid={}; original={u['unit_id']:u for p in parts for u in p['units']}
        for uid,unit in original.items():
            try: validate_units([unit],docs,segments,check_relations=False)
            except Invalid: continue
            valid[uid]=unit
        while True:
            invalid={uid for uid,u in valid.items() if any(r['target'] not in valid for r in u['relations'])}
            if not invalid: break
            for uid in invalid: valid.pop(uid)
        for part in parts:
            sid=part['source_id']
            if sid not in docs: continue
            kept=[u for u in part['units'] if u['unit_id'] in valid]
            # A changed dependency requires a fresh source pass, not a false complete checkpoint.
            if len(kept)!=len(part['units']):
                write(candidate/'retained-drafts'/f'{sid}.json',{'prior_note':part['note'],'units':kept})
                continue
            part['corpus_id']=corpus['corpus_id']
            write(candidate/'units'/f'{sid}.json',part)
        write(candidate/'source-change.json',{'previous_corpus':validate_sources(previous)[0]['corpus_id'],
              'retained_unit_ids':sorted(valid),'invalidated_unit_ids':sorted(set(original)-set(valid))})

    def attach_shared(self, selector, sources, managed_ids):
        """Set capture-owned memberships; keep manual sources and all old snapshots.

        Source runs are canonical, already normalized records. Hard links keep the
        existing self-contained snapshot paths without storing payload copies.
        """
        folder,data=self.resolve(selector); previous=self.run(folder,data)
        old,docs,_=validate_sources(previous)
        files={sid:(previous,d) for sid,d in docs.items() if sid not in managed_ids}
        for source in sources:
            _,shared,_=validate_sources(source)
            for sid,doc in shared.items():
                if sid in files: require(files[sid][1]==doc,'Shared source identity collision')
                files[sid]=(Path(source),doc)
        entries=[{'source_id':sid,'path':f'sources/{sid}.json','document_hash':fingerprint(doc)}
                 for sid,(_,doc) in sorted(files.items())]
        corpus={'schema_version':VERSION,'sources':entries,'corpus_id':'corpus-'+fingerprint(entries)}
        if corpus==old: return folder,data
        revision_id='source-'+corpus['corpus_id'].split('-')[1][:24]
        destination=folder/'sources'/revision_id
        if not destination.exists():
            with tempfile.TemporaryDirectory(prefix='.shared-',dir=folder) as temporary:
                candidate=Path(temporary)/'run'
                for area in ('sources','raw','units'): (candidate/area).mkdir(parents=True,exist_ok=True)
                for sid,(origin,doc) in files.items():
                    for relative in (f'sources/{sid}.json',doc['raw_path']):
                        try: os.link(safe_child(origin,relative),safe_child(candidate,relative))
                        except OSError as exc:
                            raise Invalid('Shared capture sources require local hard-link support on this filesystem; originals are preserved: '+str(exc)) from exc
                write(candidate/'corpus.json',corpus)
                self.carry_checkpoints(previous,candidate)
                validate_sources(candidate)
                destination.parent.mkdir(parents=True,exist_ok=True);candidate.rename(destination)
        else: require(validate_sources(destination)[0]==corpus,'Shared source revision collision')
        if revision_id not in {r['revision_id'] for r in data['revisions']}:
            data['revisions'].append({'revision_id':revision_id,'corpus_id':corpus['corpus_id'],'run':destination.relative_to(folder).as_posix()})
        history=data.get('revision_history',[r['revision_id'] for r in data['revisions']])
        if not history or history[-1]!=revision_id: history.append(revision_id)
        data['revision_history']=history;data['active_revision']=revision_id
        self.save(folder,data)
        return folder,data

    def catalog(self):
        return [self.inspect(entry['collection_id']) for entry in self.index['collections']]

    def inspect(self,selector=None):
        resolved=self.resolve(selector); require(resolved is not None,'No selected collection')
        folder,data=resolved; run=self.run(folder,data); _,docs,_=validate_sources(run)
        ir=validate_ir(run) if (run/'ir.json').exists() else None
        return {'name':data['name'],'collection_id':data['collection_id'],'archived':data.get('archived',False),
                'sources':[{'source_id':d['source_id'],'filename':d['filename'],'title':d['title'],'url':d['url']} for d in docs.values()],
                'source_count':len(docs),'knowledge_units':len(ir['units']) if ir else 0,
                'coverage':ir['coverage'] if ir else [],'source_revisions':len(data['revisions']),
                'active_revision':data['active_revision'],'knowledge_revisions':sum(len(list((safe_child(folder,r['run'])/'history').glob('*.json'))) for r in data['revisions']),
                'goals':[read(folder/'briefs'/f'{bid}.json')['objective'] for bid in data['briefs']],
                'build_count':len(data['builds']),'contradictions':sum(r['kind']=='contradicts' for u in (ir['units'] if ir else []) for r in u['relations'])}

    def set_archived(self,selector,archived):
        resolved=self.resolve(selector); require(resolved is not None,'No selected collection')
        folder,data=resolved; data['archived']=archived; self.save(folder,data)
        return self.inspect(data['collection_id'])

    def compare(self,selector=None, before=None, after=None, before_knowledge=None, after_knowledge=None):
        resolved=self.resolve(selector); require(resolved is not None,'No selected collection')
        folder,data=resolved
        def revision(key,default):
            key=key or default
            found=[r for r in data['revisions'] if r['revision_id']==key]
            require(len(found)==1,'Unknown source revision')
            run=safe_child(folder,found[0]['run']); _,docs,_=validate_sources(run)
            ir=validate_ir(run) if (run/'ir.json').exists() else None
            return run,{d['filename']:d for d in docs.values()},ir
        active=data['active_revision']; history=data.get('revision_history',[r['revision_id'] for r in data['revisions']])
        old,old_docs,old_ir=revision(before,history[-2] if len(history)>1 else active)
        new,new_docs,new_ir=revision(after,active)
        if before_knowledge: old_ir=validate_ir(old,safe_child(old,'history/'+before_knowledge+'.json'))
        if after_knowledge: new_ir=validate_ir(new,safe_child(new,'history/'+after_knowledge+'.json'))
        old_names=set(old_docs); new_names=set(new_docs)
        old_units={u['unit_id']:u for u in old_ir['units']} if old_ir else {}
        new_units={u['unit_id']:u for u in new_ir['units']} if new_ir else {}
        return {'before':old.name,'after':new.name,'added_sources':sorted(new_names-old_names),
                'before_knowledge':fingerprint(old_ir) if old_ir else None,'after_knowledge':fingerprint(new_ir) if new_ir else None,
                'removed_sources':sorted(old_names-new_names),
                'changed_sources':sorted(k for k in old_names&new_names if fingerprint(old_docs[k])!=fingerprint(new_docs[k])),
                'knowledge_comparison_available':old_ir is not None and new_ir is not None,
                'added_units':sorted(set(new_units)-set(old_units)) if new_ir is not None else None,
                'removed_units':sorted(set(old_units)-set(new_units)) if new_ir is not None else None,
                'changed_units':sorted(k for k in old_units.keys()&new_units.keys() if old_units[k]!=new_units[k]) if new_ir is not None else None,
                'preserved_builds':len(data['builds'])}

    @staticmethod
    def run(folder, data):
        revision = next(r for r in data['revisions'] if r['revision_id'] == data['active_revision'])
        return safe_child(folder, revision['run'])
