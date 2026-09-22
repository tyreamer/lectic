"""Generic capture contracts; goal prose/extraction are authored semantic fixtures."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from support import isolate_home
import ec
from capture_store import CaptureStore, capture_command
from capture_write import save_capture
from collection_store import Library
from goal_workflow import work, validate_build


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.project=self.base/'Local Project';self.project.mkdir()
        self.home=isolate_home(self,self.base)
        self.inbox=self.base/'Synced Inbox';self.inbox.mkdir()
        self.store=CaptureStore(self.project)
        self.cases=ec.read(ec.ROOT/'fixtures/capture/workflows.json')

    def tearDown(self): self.temp.cleanup()

    def capture(self,**kwargs):
        path=save_capture(self.inbox,**kwargs);return ec.read(path)['capture_id']

    def imported(self): return capture_command(project=self.project,action='import',inbox=self.inbox)

    def rows(self,collection=None): return self.store.listing(collection)['items']

    def source_run(self,name):
        library=Library(self.project);folder,data=library.resolve(name);return library.run(folder,data)

    def seed(self,name):
        run=self.source_run(name);corpus,docs,_=ec.validate_sources(run)
        for doc in docs.values():
            segment=doc['segments'][0];uid='unit-'+doc['source_id'][4:20]
            unit={'schema_version':'1.0','unit_id':uid,'type':'procedure','status':'explicit','title':doc['title'] or 'Supplied procedure',
                'statement':segment['text'],'scope':'Only the supplied excerpt; missing details remain unknown.',
                'derivation':'','evidence':[{'source_id':doc['source_id'],'segment_id':segment['segment_id'],'quote':segment['text']}],
                'attribution':[],'relations':[]}
            ec.write(run/'units'/f"{doc['source_id']}.json",{'schema_version':'1.0','corpus_id':corpus['corpus_id'],
                'source_id':doc['source_id'],'note':'Authored semantic acceptance checkpoint; not model output.','units':[unit]})
        self.assertEqual(work(project=self.project,collection=name,action='prepare',reconciled=True)['phase'],'knowledge_saved')
        return run

    def prepare_case(self,case):
        for item in case['captures']:
            self.capture(text=item.get('text',''),url=item.get('url',''),title=item['title'],note=item['note'],collections=[case['collection']])
        self.imported();result=self.store.process(case['collection']);self.assertEqual(result['phase'],'extract')
        return self.seed(case['collection'])

    def finish(self,case):
        brief={'schema_version':'1.0','intent':case['intent'],'intent_reason':'Apply saved source methods to the requested work.',
            'objective':case['goal'],'context':'Authored cross-domain fixture.','constraints':['Preserve unknown details and source boundaries.'],
            'work':{'label':'User context','text':case['work']},'desired_result':case['goal'],
            'success_criteria':['Produce useful work without inventing missing source content.']}
        path=self.project/'brief.json';ec.write(path,brief)
        result=work(project=self.project,collection=case['collection'],brief=str(path));self.assertEqual(result['phase'],'assess_coverage')
        task=result['agent_task'];draft=Path(task['draft']);ir=ec.validate_ir(result['run']);ids=[u['unit_id'] for u in ir['units']]
        ec.write(draft/'coverage.json',{'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
            'decision':'reuse','source_ids':[],'reason':'Supplied text supports a bounded outcome with explicit gaps.','unsupported':case['unsupported']})
        cap={'schema_version':'1.0','capability_id':'saved-source-method','title':'Apply saved source methods',
            'description':'Apply relevant supplied procedures and disclose missing details.','rationale':'Reuse actually captured text.',
            'inputs':'A user task and its constraints.','output_contract':'Source-backed work and unresolved questions.',
            'unit_ids':ids,'steps':[{'instruction':u['statement'],'unit_ids':[u['unit_id']]} for u in ir['units']],
            'boundaries':case['limitations'],'conflict_policy':'Preserve disagreements; personal notes are not source authority.',
            'checks':['No missing source detail was invented.'],
            'examples':[{'input':'An incomplete source excerpt.','output':'Use the supplied details and identify what remains unknown.','unit_ids':ids,'status':'synthetic'}]}
        method={'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],'capability':cap}
        ec.write(draft/'method.json',method)
        self.assertEqual(work(project=self.project)['phase'],'apply_method')
        ec.write(draft/'result.json',{'schema_version':'1.1','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
            'method_hash':ec.fingerprint(method),'target':case['intent'],'summary':'Bounded outcome using saved source excerpts.',
            'sections':[{'kind':kind,'title':title,'content':content,'status':'synthesized','unit_ids':ids} for kind,title,content in case['result_sections']],
            'disagreements':[],'limitations':case['limitations'],'unsupported':case['unsupported'],'additional_general_advice':[]})
        done=work(project=self.project,reviewed=True);self.assertEqual(done['phase'],'complete')
        self.assertTrue(validate_build(done['build'])['valid']);return Path(done['build'])

    def test_capture_is_cheap_defaults_to_inbox_no_source_or_ir(self):
        cid=self.capture(url='https://example.com/talk',note='Interesting, not endorsement.')
        report=self.imported();self.assertTrue(report['items'][0]['saved']);self.assertFalse(report['items'][0]['processing_performed'])
        row=self.rows('Inbox')[0];self.assertEqual(row['capture_id'],cid)
        self.assertEqual(row['processing_status'],'awaiting_retrieval')
        self.assertEqual(row['source_ids'],[])
        self.assertFalse(list(self.home.rglob('ir.json')))

    def test_reimport_is_idempotent_before_and_after_processing(self):
        self.capture(text='First inspect the input before changing the configuration.')
        self.imported();self.assertFalse(self.imported()['items'][0]['new'])
        self.store.process('Inbox');self.seed('Inbox')
        first=self.source_run('Inbox');original=(first/'ir.json').read_bytes()
        self.imported();result=self.store.process('Inbox')
        self.assertEqual(result['phase'],'knowledge_saved');self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.source_run('Inbox'),first);self.assertEqual((first/'ir.json').read_bytes(),original)
        self.assertEqual(self.rows()[0]['processing_status'],'processed')

    def test_same_source_two_captures_retains_notes_without_source_duplication(self):
        text='Check the principal before authorizing an action.'
        self.capture(text=text,note='Useful.',collections=['AI Architecture'])
        self.capture(text=text,note='Do not treat as policy.',collections=['AI Architecture'])
        self.imported();self.store.process('AI Architecture')
        rows=self.rows();self.assertEqual(len(rows),2);self.assertEqual(rows[0]['source_ids'],rows[1]['source_ids'])
        self.assertEqual(len(ec.validate_sources(self.source_run('AI Architecture'))[1]),1)
        self.assertEqual(len(list((self.store.root/'sources').iterdir())),1)

    def test_multi_collection_shared_payload_and_membership_removal_preserves_history(self):
        cid=self.capture(text='Check principal, action and resource.',collections=['AI Architecture','Security'])
        self.imported();self.store.process('AI Architecture');self.seed('AI Architecture')
        result=self.store.process('Security');self.assertEqual(len(result['reused_capture_sources']),1)
        a=self.source_run('AI Architecture');b=self.source_run('Security')
        sid=self.rows()[0]['source_ids'][0];doc=ec.validate_sources(a)[1][sid]
        canonical=self.store.root/'sources'/sid
        self.assertTrue((a/doc['raw_path']).samefile(b/doc['raw_path']))
        self.assertTrue((a/doc['raw_path']).samefile(canonical/doc['raw_path']))
        self.store.membership([cid],['AI Architecture'],'remove')
        self.assertEqual(len(ec.validate_sources(self.source_run('AI Architecture'))[1]),0)
        self.assertEqual(len(ec.validate_sources(self.source_run('Security'))[1]),1)
        self.assertEqual(len(ec.validate_sources(a)[1]),1)
        self.assertEqual(self.rows()[0]['collections'],['Security'])

    def test_move_multiple_items_and_last_membership_returns_to_inbox(self):
        ids=[self.capture(text=f'Supplied text {i}.') for i in range(3)];self.imported()
        self.store.membership(ids,['Dinner Ideas'],'move')
        self.assertEqual(len(self.rows('Inbox')),0);self.assertEqual(len(self.rows('Dinner Ideas')),3)
        self.store.membership(ids,['Dinner Ideas'],'remove')
        self.assertEqual(len(self.rows('Inbox')),3)

    def test_move_reuses_historical_extraction_and_legacy_add_preserves_shared_storage(self):
        cid=self.capture(text='Inspect permission boundaries first.',collections=['AI Architecture'])
        self.imported();self.store.process('AI Architecture');old=self.seed('AI Architecture')
        sid=self.rows()[0]['source_ids'][0];doc=ec.validate_sources(old)[1][sid]
        extra=self.base/'new-input';extra.mkdir();(extra/'extra.txt').write_text('A separate supplied source.',encoding='utf-8')
        work(project=self.project,collection='AI Architecture',action='add',input=str(extra))
        self.assertTrue((self.source_run('AI Architecture')/doc['raw_path']).samefile(old/doc['raw_path']))
        self.store.membership([cid],['Security'],'move')
        result=self.store.process('Security')
        self.assertEqual(result['reused_capture_sources'],[sid]);self.assertEqual(result['phase'],'reconcile')

    def test_annotation_event_saved_after_capture_is_separate_and_idempotent(self):
        cid=self.capture(text='A source procedure.');self.imported()
        record=(self.store.root/'records'/f'{cid}.json').read_bytes()
        note={'schema_version':'1.0','annotation_id':'annotation-test','capture_id':cid,'annotated_at':'2026-09-15T12:00:00Z',
              'user_note':'Do not treat as company policy.','add_collections':['AI Architecture','Security']}
        ec.write(self.inbox/'annotation-test.note.json',note)
        self.imported();self.imported()
        self.assertEqual(len(self.store.load(cid)[1]['annotation_ids']),1)
        self.assertEqual((self.store.root/'records'/f'{cid}.json').read_bytes(),record)
        self.assertIn('Security',self.rows()[0]['collections'])
        self.assertIn('company policy',self.rows()[0]['user_context'][0]['note'])

    def test_annotation_before_parent_retries_when_parent_arrives(self):
        note={'schema_version':'1.0','annotation_id':'annotation-early','capture_id':'capture-later','annotated_at':'2026-09-15T12:00:00Z',
              'user_note':'Keep this context.','add_collections':[]}
        ec.write(self.inbox/'annotation-early.note.json',note)
        self.assertEqual(len(self.imported()['needs_attention']),1)
        self.capture(text='A supplied observation.',capture_id='capture-later')
        self.assertFalse(self.imported()['needs_attention']);self.assertEqual(len(self.rows()[0]['user_context']),1)

    def test_notes_cannot_be_cited_as_source_evidence(self):
        self.capture(text='Test expiry separately from revocation.',note='Definitely company policy.')
        self.imported();self.store.process('Inbox');run=self.seed('Inbox')
        ir=ec.validate_ir(run);unit=copy.deepcopy(ir['units'][0]);unit['evidence'][0]['quote']='Definitely company policy.'
        _,docs,segments=ec.validate_sources(run)
        with self.assertRaises(ec.Invalid): ec.validate_units([unit],docs,segments)
        self.assertNotIn('Definitely company policy',json.dumps(ir))

    def test_late_attachment_retried_and_hash_mismatch_not_accepted(self):
        file=self.base/'notes.txt';file.write_text('Supplied note content.',encoding='utf-8')
        cid=self.capture(files=[file]);event=ec.read(self.inbox/f'{cid}.json')
        attachment=self.inbox/event['attachments'][0]['path'];raw=attachment.read_bytes();attachment.unlink()
        self.imported();self.assertEqual(self.rows()[0]['processing_status'],'needs_attention')
        attachment.write_bytes(b'incomplete');self.imported();self.assertEqual(self.rows()[0]['source_ids'],[])
        attachment.write_bytes(raw);self.assertFalse(self.imported()['items'][0]['issues'])
        self.store.process('Inbox');self.assertEqual(len(self.rows()[0]['source_ids']),1)

    def test_images_video_and_pdf_preserved_without_ocr_or_transcription(self):
        for filename in ['image.png','video.mp4','document.pdf']:
            file=self.base/filename;file.write_bytes(b'opaque fixture bytes');self.capture(files=[file])
        self.imported();self.store.process('Inbox')
        for row in self.rows():
            self.assertEqual(row['source_ids'],[]);self.assertEqual(row['processing_status'],'needs_attention')
        self.assertEqual(len(list((self.home/'blobs').iterdir())),1)  # identical bytes are one canonical blob

    def test_link_with_shared_excerpt_is_partial_not_retrieved(self):
        self.capture(url='https://example.com/talk',text='Check action boundaries before permitting a tool call.')
        self.imported();self.store.process('Inbox');self.seed('Inbox')
        self.assertEqual(self.rows()[0]['processing_status'],'partially_processed')
        self.assertIn('not yet retrieved',self.rows()[0]['retrieval'])

    def test_invalid_timestamp_metadata_and_path_escape_are_reported(self):
        cid=self.capture(text='Valid supplied content.');path=self.inbox/f'{cid}.json';event=ec.read(path)
        for mutation in [{'captured_at':'2026-09-15'}, {'unexpected':'field'},
                         {'attachments':[{'path':'../outside.txt','filename':'outside.txt'}]}]:
            ec.write(path,{**event,**mutation})
            self.assertTrue(self.imported()['needs_attention'])
        self.assertEqual(self.rows(),[])

    def test_capture_id_collision_and_changed_attachment_are_not_overwritten(self):
        cid=self.capture(text='Original value.');self.imported();path=self.inbox/f'{cid}.json'
        changed=ec.read(path);changed['shared_text']='Changed content.';ec.write(path,changed)
        self.assertTrue(self.imported()['needs_attention'])
        self.assertEqual(self.store.load(cid)[0]['shared_text'],'Original value.')

    def test_search_time_range_and_notes(self):
        self.capture(text='A talk.',note='Important agent architecture boundaries.',captured_at='2026-09-15T12:00:00Z')
        self.capture(text='An older talk.',note='Agent architecture.',captured_at='2026-09-01T12:00:00Z')
        self.imported()
        found=self.store.listing(query='agent architecture',since='2026-09-14T00:00:00-04:00',until='2026-09-21T00:00:00-04:00')['items']
        self.assertEqual(len(found),1)

    def test_fresh_installed_cli_import_and_list(self):
        from install_skill import install
        self.capture(text='Shared text with a quote: "hello" and a newline.\nNo JSON escaping problem.')
        installed=install(self.base/'Installed Skills/expertise-compiler')
        command=[sys.executable,'-X','utf8','-B',str(installed/'scripts/ec.py'),'capture','--project',str(self.project)]
        for args in [['--action','import','--inbox',str(self.inbox)],['--action','list','--collection','Inbox']]:
            process=subprocess.run(command+args,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(process.returncode,0,process.stderr);self.assertTrue(json.loads(process.stdout)['items'])

    def test_shortcut_sample_envelopes_and_non_uuid_ids(self):
        for name in ['shortcut-url.json','shortcut-annotation.note.json']:
            (self.inbox/name).write_bytes((ec.ROOT/'fixtures/capture'/name).read_bytes())
        report=self.imported();self.assertFalse(report['needs_attention'])
        self.assertEqual(len(report['items']),1);self.assertEqual(len(report['annotations']),1)
        self.capture(text='Supplied text.',capture_id='capture-20260915120000123-12345678-87654321')
        self.assertFalse(self.imported()['needs_attention'])
        self.assertEqual(len(self.rows()),2)

    def test_unicode_share_survives_legacy_windows_output_encoding(self):
        self.capture(text='A useful \u65b9\u6cd5 \U0001f35d',note='Try \u00e9 and "quoted" text.')
        self.imported()
        process=subprocess.run([sys.executable,'-B',str(ec.ROOT/'scripts/ec.py'),'capture','--project',str(self.project)],
            capture_output=True,text=True,encoding='ascii',env={**os.environ,'PYTHONIOENCODING':'cp1252'})
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn('\U0001f35d',json.loads(process.stdout)['items'][0]['title'])

    def test_personal_workflow_keeps_unknown_quantities_and_unretrieved_items_visible(self):
        case=self.cases[0];run=self.prepare_case(case);build=self.finish(case)
        result=ec.read(build/'result.json');text=' '.join(s['content'] for s in result['sections'])
        self.assertIn('quantities unknown',text);self.assertIn('provisional',result['limitations'][1])
        self.assertTrue(any('not been retrieved' in item for item in result['unsupported']))
        self.assertEqual(len(ec.validate_sources(run)[1]),3)
        self.assertIn("Probably wouldn't make the side dish",ec.read(build/'brief.json')['context'])
        self.assertNotIn("Probably wouldn't make the side dish",json.dumps(ec.validate_ir(run)))
        trace=self.store.trace(build);self.assertEqual(len(trace['captures']),3)

    def test_builder_workflow_note_and_evidence_survive_new_source_and_annotation(self):
        case=self.cases[1];self.prepare_case(case);build=self.finish(case)
        original=(build/'brief.json').read_bytes();original_result=(build/'result.json').read_bytes()
        self.assertIn('do not treat this as company policy',ec.read(build/'brief.json')['context'])
        cid=self.rows(case['collection'])[0]['capture_id']
        capture_command(project=self.project,action='note',items=[cid],note='New interpretation for future use.')
        self.capture(text='Record the owner of each authorization decision.',collections=[case['collection']]);self.imported()
        self.store.process(case['collection'])
        self.assertTrue(validate_build(build)['valid'])
        self.assertEqual((build/'brief.json').read_bytes(),original);self.assertEqual((build/'result.json').read_bytes(),original_result)
        trace=self.store.trace(build);self.assertEqual(len(trace['captures']),2)
        self.assertNotIn('New interpretation for future use',trace['saved_user_context'])


if __name__=='__main__': unittest.main()
