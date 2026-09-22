"""Authored semantic fixtures exercise orchestration; these are not live AI results."""
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from collection_store import Library
from goal_workflow import work, validate_build, GOAL_QUESTION
import test_workflow


class GoalTests(unittest.TestCase):
    seed = test_workflow.WorkflowTests.seed

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / 'Actual Work'; self.project.mkdir()
        self.home = isolate_home(self, self.base)
        self.oracle = None

    def tearDown(self):
        self.temp.cleanup()

    def brief(self, domain='debugging', suffix='first'):
        text = {'debugging':'PRIVATE DRAFT: Change parsing and delimiters together, then ship after one successful file.',
                'photography':'PRIVATE DRAFT: My background is sharp but the subject is blurry. Increase shutter speed to fix focus.'}[domain]
        brief = {'schema_version':'1.0','objective':'Improve my ' + domain + ' plan ' + suffix,
                 'context':'I need a repeatable process for a small project.','constraints':['Use supplied methods.'],
                 'work':{'label':'My original plan','text':text},'desired_result':'A practical improved plan',
                 'success_criteria':['Identify unsupported assumptions and concrete next tests.']}
        path = self.project / ('brief-' + suffix + '.json'); ec.write(path,brief)
        return path

    def start(self, domain='debugging'):
        result = work(project=self.project,input=str(ec.ROOT / 'fixtures' / domain),name='My Methods',brief=str(self.brief(domain)))
        self.assertEqual(result['phase'],'extract')
        self.seed(result['run'])
        return work(project=self.project,reconciled=True)

    def finish(self, result, target='review'):
        self.assertEqual(result['phase'],'assess_coverage')
        task=result['agent_task']; draft=Path(task['draft']); ir=ec.validate_ir(result['run'])
        ids={u['unit_id'] for u in ir['units']}
        cap=next(c for c in reversed(ec.read(ec.ROOT / 'fixtures/demo_capabilities.json')) if set(c['unit_ids']) <= ids)
        ec.write(draft / 'coverage.json',{'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
                 'decision':'reuse','source_ids':[],'reason':'Authored test: relevant procedures are present.','unsupported':['No guarantee of a universal fix.']})
        method={'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],'capability':cap}
        self.assertEqual(work(project=self.project,target=target)['phase'],'design_method')
        ec.write(draft / 'method.json',method)
        self.assertEqual(work(project=self.project,target=target)['phase'],'apply_method')
        debug='debug-isolate' in ids
        finding={'title':'Isolate the suspected cause' if debug else 'Check focus before shutter speed',
                 'priority':'high','assessment':'Your plan skips a distinction required by the supplied method.',
                 'proposed_change':'Change one suspected cause at a time and revert ineffective changes.' if debug else 'Check which plane is sharp before treating blur as camera shake.',
                 'unit_ids':['debug-isolate' if debug else 'photo-focus']}
        result_data={'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],'method_hash':ec.fingerprint(method),
                     'target':target,'assessment':'Revise the test plan before relying on it.','findings':[finding],
                     'proposed_revision':finding['proposed_change'],
                     'checklist':[{'action':finding['proposed_change'],'done_when':'The relevant test and outcome are recorded.','unit_ids':finding['unit_ids']}] if target=='checklist' else [],
                     'disagreements':[],'limitations':['Synthetic fixture; semantic quality has not been independently tested.'],
                     'unsupported':['Universal correctness.'],'additional_general_advice':[]}
        ec.write(draft / 'result.json',result_data)
        self.assertEqual(work(project=self.project,target=target)['phase'],'review_result')
        completed=work(project=self.project,target=target,reviewed=True)
        self.assertEqual(completed['phase'],'complete')
        return completed

    def test_clear_goal_completes_actual_review_in_unrelated_domains(self):
        for domain in ['debugging','photography']:
            with self.subTest(domain=domain):
                self.project=self.base / domain; self.project.mkdir()
                self.home=isolate_home(self,self.project)
                result=self.finish(self.start(domain))
                self.assertTrue(validate_build(result['build'])['valid'])
                rendered=Path(result['result']).read_text(encoding='utf-8')
                self.assertIn('Proposed change',rendered)
                for link in re.findall(r'\]\(([^)]+)\)',rendered):
                    self.assertTrue((Path(result['build']) / link).exists(),link)
                self.assertIn('PRIVATE DRAFT',ec.read(Path(result['build']) / 'brief.json')['work']['text'])

    def test_missing_goal_asks_once(self):
        first=work(project=self.project,input=str(ec.ROOT / 'fixtures/debugging'))
        self.assertEqual(first['phase'],'needs_goal'); self.assertEqual(first['message'],GOAL_QUESTION)
        second=work(project=self.project)
        self.assertTrue(second['already_asked']); self.assertIsNone(second['message'])

    def test_archive_only_and_explore_never_force_a_build(self):
        result=work(project=self.project,input=str(ec.ROOT / 'fixtures/photography'),name='Saved Research',action='save')
        self.assertEqual(result['phase'],'archived')
        self.assertEqual(ec.read(Path(result['collection_location']) / 'collection.json')['builds'],[])
        self.assertEqual(work(project=self.project,action='explore')['phase'],'extract')

    def test_fresh_process_uses_named_collection_on_second_task(self):
        first=self.finish(self.start())
        command=[sys.executable,'-B',str(ec.ROOT / 'scripts/ec.py'),'work','--project',str(self.project),
                 '--collection','My Methods','--brief',str(self.brief(suffix='second'))]
        process=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        second=self.finish(json.loads(process.stdout))
        self.assertNotEqual(first['build'],second['build'])
        report=ec.read(Path(second['build']) / 'validation.json')
        self.assertEqual(len(report['reuse']['reused_units']),3)
        self.assertEqual(report['reuse']['new_units'],[])
        self.assertTrue(validate_build(first['build'])['valid'])

    def test_same_collection_new_goal_checklist(self):
        first=self.finish(self.start())
        result=work(project=self.project,brief=str(self.brief(suffix='team-checklist')),target='checklist')
        second=self.finish(result,'checklist')
        self.assertIn('- [ ]',Path(second['result']).read_text(encoding='utf-8'))
        self.assertNotEqual(first['build'],second['build'])

    def test_insufficient_extraction_requests_source_pass_and_records_extension(self):
        result=self.start(); task=result['agent_task']; draft=Path(task['draft'])
        _,docs,_=ec.validate_sources(result['run']); sid=next(iter(docs))
        ec.write(draft / 'coverage.json',{'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
                 'decision':'extend','source_ids':[sid],'reason':'Recheck applicability for this goal.','unsupported':[]})
        self.assertEqual(work(project=self.project)['phase'],'extend_sources')
        checkpoint=Path(result['run']) / f'units/{sid}.json'
        part=ec.read(checkpoint); extra=copy.deepcopy(part['units'][0]); extra['unit_id']='additional-source-pass-unit'
        part['units'].append(extra); ec.write(checkpoint,part)
        self.assertEqual(work(project=self.project)['phase'],'reconcile')
        result=work(project=self.project,reconciled=True)
        completed=self.finish(result)
        reuse=ec.read(Path(completed['build']) / 'validation.json')['reuse']
        self.assertIn('additional-source-pass-unit',reuse['new_units'])
        self.assertEqual(reuse['source_passes_requested'],[sid])
        self.assertEqual(len(list((draft / 'coverage-history').glob('*.json'))),2)

    def test_added_sources_preserve_old_build_and_dependencies(self):
        first=self.finish(self.start())
        added=work(project=self.project,input=str(ec.ROOT / 'fixtures/photography'),collection='My Methods',action='add')
        self.assertEqual(added['revision_count'],2)
        self.assertNotEqual(added['run'],first['run'])
        resumed=work(project=self.project)
        self.assertEqual(resumed['phase'],'extract')
        self.assertEqual(len(resumed['agent_task']['pending_sources']),1)
        self.seed(resumed['run'])
        second=self.finish(work(project=self.project,reconciled=True))
        self.assertNotEqual(ec.read(Path(first['build']) / 'manifest.json')['source_revision'],ec.read(Path(second['build']) / 'manifest.json')['source_revision'])
        self.assertTrue(validate_build(first['build'])['valid'])
        reuse=ec.read(Path(second['build']) / 'validation.json')['reuse']
        self.assertEqual(len(reuse['reused_units']),3); self.assertEqual(len(reuse['new_units']),3)

    def test_export_scopes_sources_and_excludes_user_work(self):
        first=self.finish(self.start())
        result=work(project=self.project,action='export'); package=Path(result['skill']).parent
        ec.validate_package(package)
        self.assertFalse((package / 'sources/raw').exists())
        self.assertFalse((package / 'brief.json').exists())
        self.assertFalse(any('PRIVATE DRAFT' in p.read_text(encoding='utf-8') for p in package.rglob('*') if p.is_file()))
        self.assertTrue(any((Path(first['run']) / 'raw').rglob('*')))
        # Adding a private file cannot be hidden by regenerating its inventory.
        ec.write(package / 'private.json',{'secret':'private'})
        manifest=ec.read(package / 'manifest.json'); manifest['files']=ec.inventory(package); ec.write(package / 'manifest.json',manifest)
        with self.assertRaisesRegex(ec.Invalid,'private files'): ec.validate_package(package)

    def test_artifact_tampering_and_stale_review_block_completion(self):
        complete=self.finish(self.start()); build=Path(complete['build'])
        (build / 'result.md').write_text('Invented completion',encoding='utf-8')
        with self.assertRaisesRegex(ec.Invalid,'hash mismatch'): validate_build(build)
        with self.assertRaises(ec.Invalid): work(project=self.project)

    def test_legacy_adoption_leaves_original_bytes_unchanged(self):
        from demo import build
        original=build(self.base / 'old-run')
        before=ec.inventory(original)
        result=work(project=self.project,adopt=str(original),name='Adopted',action='save')
        self.assertEqual(result['phase'],'archived')
        self.assertNotEqual(Path(result['run']),original)
        self.assertEqual(before,ec.inventory(original))
        self.assertEqual(ec.validate_ir(original),ec.validate_ir(result['run']))

    def test_installed_goal_entrypoint_keeps_data_in_project(self):
        from install_skill import install
        installed=install(self.base / 'Skills/expertise-compiler')
        before=ec.inventory(installed)
        command=[sys.executable,'-B',str(installed / 'scripts/ec.py'),'work','--project',str(self.project),
                 '--input',str(installed / 'fixtures/debugging'),'--brief',str(self.brief())]
        process=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout)['phase'],'extract')
        self.assertEqual(ec.inventory(installed),before)
        self.assertTrue((self.home / 'library.json').exists())
        self.assertFalse((self.project / '.expertise-compiler').exists())

    def test_comparison_has_same_sources_context_and_empty_effort_observations(self):
        from evaluate import prepare_comparison, score
        result=self.finish(self.start()); build=Path(result['build']); output=self.project / 'comparison'
        prepare_comparison(result['run'],Path(result['method']).parent,output,
                           ec.ROOT / 'fixtures/flows/debugging-tasks.json',ec.ROOT / 'fixtures/flows/debugging-rubric.json',build / 'brief.json')
        baseline=(output / 'baseline-prompt.md').read_text(encoding='utf-8')
        compiled=(output / 'compiled-prompt.md').read_text(encoding='utf-8')
        context=ec.read(build / 'brief.json')
        for prompt in [baseline,compiled]:
            self.assertIn(context['work']['text'],prompt)
            self.assertIn('RAW TRANSCRIPTS',prompt)
            self.assertIn('retain your own notes',prompt)
            self.assertNotIn('expected_decisions',prompt)
        observations=ec.read(output / 'effort.json')['observations']
        self.assertEqual(len(observations),6)
        self.assertTrue(all(o['quality_rating'] is None and o['active_user_minutes'] is None for o in observations))
        ec.write(output / 'context.json',{'objective':'Changed goal'})
        with self.assertRaisesRegex(ec.Invalid,'Shared context changed'):
            score(result['run'],output / 'response-template.json','compiled',output)

    def test_malformed_brief_and_library_fail_cleanly(self):
        brief=self.brief(); value=ec.read(brief); value['constraints']='not an array'; ec.write(brief,value)
        with self.assertRaises(ec.Invalid):
            work(project=self.project,input=str(ec.ROOT / 'fixtures/debugging'),brief=str(brief))
        ec.write(self.home / 'library.json',{'schema_version':'1.0','collections':[{'name':'broken'}]})
        with self.assertRaisesRegex(ec.Invalid,'Malformed collection entry'): Library(self.project)


if __name__=='__main__': unittest.main()
