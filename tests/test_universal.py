"""Domain-neutral orchestration contracts with explicit authored semantic fixtures.

These tests do not call a model or prove natural-language skill activation.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from support import isolate_home
import ec
from collection_store import Library
from goal_workflow import work,validate_build
from outcomes import INTENTS,validate_outcome


class UniversalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.base=Path(self.temp.name).resolve()
        self.project=self.base/'Project'; self.project.mkdir()
        self.home=isolate_home(self,self.base)
        self.cases=ec.read(ec.ROOT/'fixtures/universal/cases.json')

    def tearDown(self): self.temp.cleanup()

    def brief(self,case,suffix=''):
        brief={'schema_version':'1.0','intent':case['intent'],'intent_reason':case['reason'],
               'objective':case['request'],'context':'Synthetic acceptance input.','constraints':['Use the supplied source scope.'],
               'work':{'label':'Supplied task input','text':case.get('work','')},
               'desired_result':case['intent'].title()+' result','success_criteria':['Produce useful work with evidence and honest limits.']}
        path=self.project/('brief'+suffix+'.json');ec.write(path,brief);return path

    def seed(self,run,case,count=2):
        corpus,docs,_=ec.validate_sources(run)
        doc=next(d for d in docs.values() if d['filename']=='source.txt')
        units=[]
        for i,quote in enumerate(case['source'][:count]):
            seg=next(s for s in doc['segments'] if quote in s['text'])
            units.append({'schema_version':'1.0','unit_id':'rule-'+str(i+1),'type':'principle','status':'explicit',
                          'title':'Source rule '+str(i+1),'statement':quote,'scope':'Synthetic lesson only.',
                          'derivation':'','evidence':[{'source_id':doc['source_id'],'segment_id':seg['segment_id'],'quote':quote}],
                          'attribution':[],'relations':[]})
        ec.write(Path(run)/'units'/f"{doc['source_id']}.json",{'schema_version':'1.0','corpus_id':corpus['corpus_id'],
                 'source_id':doc['source_id'],'note':'Authored fixture checkpoint: reviewed supplied lines; '+('second rule deferred for targeted extraction.' if count==1 else 'both rules extracted.'),'units':units})

    def start(self,case,count=2):
        result=work(project=self.project,input=str(ec.ROOT/'fixtures/universal'/case['domain']),name='Reusable Methods',brief=str(self.brief(case)))
        self.assertEqual(result['phase'],'extract')
        self.assertEqual(result['agent_task']['target'],case['intent'])
        self.seed(result['run'],case,count)
        return work(project=self.project,reconciled=True)

    def finish(self,result,case):
        self.assertEqual(result['phase'],'assess_coverage')
        task=result['agent_task']; draft=Path(task['draft']); ir=ec.validate_ir(result['run'])
        ids=[u['unit_id'] for u in ir['units']]
        ec.write(draft/'coverage.json',{'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
                 'decision':'reuse','source_ids':[],'reason':'Authored fixture: current rules suffice for this task.','unsupported':[]})
        cap={'schema_version':'1.0','capability_id':'source-method','title':'Source method','description':'Apply the relevant supplied rules to the user goal.',
             'rationale':'Make a repeatable source-backed method.','inputs':'User objective and relevant context.','output_contract':'Useful outcome with evidence and limits.',
             'unit_ids':ids,'steps':[{'instruction':u['statement'],'unit_ids':[u['unit_id']]} for u in ir['units']],
             'boundaries':['Synthetic lesson scope only.'],'conflict_policy':'Preserve any recorded disagreements.',
             'checks':['Does each source-derived conclusion retain evidence?'],
             'examples':[{'input':'An unrelated synthetic application.','output':'Use the relevant source rule and identify limits.','unit_ids':ids,'status':'synthetic'}]}
        method={'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],'capability':cap}
        self.assertEqual(work(project=self.project)['phase'],'design_method')
        ec.write(draft/'method.json',method)
        self.assertEqual(work(project=self.project)['phase'],'apply_method')
        outcome={'schema_version':'1.1','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],'method_hash':ec.fingerprint(method),
                 'target':case['intent'],'summary':'Completed the supplied synthetic task.',
                 'sections':[{'kind':kind,'title':title,'content':content,'status':status,'unit_ids':ids} for kind,title,content,status in case['sections']],
                 'disagreements':[],'limitations':['Authored semantic fixture, not a live model effectiveness result.'],
                 'unsupported':[],'additional_general_advice':[]}
        ec.write(draft/'result.json',outcome)
        self.assertEqual(work(project=self.project)['phase'],'review_result')
        done=work(project=self.project,reviewed=True)
        self.assertEqual(done['phase'],'complete')
        self.assertTrue(validate_build(done['build'])['valid'])
        return done

    def test_eight_intents_six_domains_same_coordinator(self):
        self.assertEqual({c['intent'] for c in self.cases},set(INTENTS))
        self.assertEqual(len({c['domain'] for c in self.cases}),6)
        for case in self.cases:
            with self.subTest(intent=case['intent'],domain=case['domain']):
                self.project=self.base/case['intent'];self.project.mkdir()
                self.home=isolate_home(self,self.project)
                done=self.finish(self.start(case),case)
                build=Path(done['build'])
                self.assertTrue((build/'method.md').exists())
                self.assertFalse(any(build.rglob('SKILL.md')))
                self.assertFalse((self.home/'exports').exists())
                self.assertIn(case['sections'][0][2],(build/'result.md').read_text(encoding='utf-8'))
                saved=ec.read(build/'brief.json')
                self.assertEqual(saved['intent_reason'],case['reason'])
                self.assertEqual(saved['objective'],case['request'])

    def test_new_goal_fresh_process_reuses_ir_and_exports_only_when_requested(self):
        first=next(c for c in self.cases if c['intent']=='decide')
        done=self.finish(self.start(first),first)
        second=next(c for c in self.cases if c['intent']=='reference')
        from install_skill import install
        installed=install(self.base/'Installed Skills/expertise-compiler')
        cli=[sys.executable,'-B',str(installed/'scripts/ec.py'),'work','--project',str(self.project),
             '--collection','Reusable Methods','--brief',str(self.brief(second,'-next'))]
        process=subprocess.run(cli,capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        reused=self.finish(json.loads(process.stdout),second)
        self.assertNotEqual(done['build'],reused['build'])
        self.assertEqual(ec.read(Path(done['build'])/'manifest.json')['ir_hash'],ec.read(Path(reused['build'])/'manifest.json')['ir_hash'])
        self.assertEqual(len(ec.read(Path(reused['build'])/'validation.json')['reuse']['reused_units']),2)
        exported=work(project=self.project,action='export'); folder=Path(exported['skill']).parent
        ec.validate_package(folder)
        self.assertFalse((folder/'brief.json').exists());self.assertFalse((folder/'result.json').exists())
        self.assertTrue(validate_build(done['build'])['valid'])

    def test_new_goal_extends_knowledge_without_destroying_old_build(self):
        first=next(c for c in self.cases if c['intent']=='create')
        done=self.finish(self.start(first,count=1),first)
        new=copy.deepcopy(first);new.update(intent='reference',request='What should an objection do?',reason='Ask a source-backed question.',sections=[['answer','Answer',first['source'][1],'explicit']])
        r=work(project=self.project,brief=str(self.brief(new,'-question')))
        task=r['agent_task'];draft=Path(task['draft']); sid=next(iter(ec.validate_sources(r['run'])[1]))
        ec.write(draft/'coverage.json',{'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
                 'decision':'extend','source_ids':[sid],'reason':'The question needs the previously deferred second rule.','unsupported':[]})
        self.assertEqual(work(project=self.project)['phase'],'extend_sources')
        self.seed(r['run'],new,count=2)
        self.assertEqual(work(project=self.project)['phase'],'reconcile')
        fresh=self.finish(work(project=self.project,reconciled=True),new)
        report=ec.read(Path(fresh['build'])/'validation.json')['reuse']
        self.assertEqual(report['new_units'],['rule-2']);self.assertEqual(report['reused_units'],['rule-1'])
        self.assertTrue(validate_build(done['build'])['valid'])
        old_hash=ec.read(Path(done['build'])/'manifest.json')['ir_hash']
        changes=work(project=self.project,action='compare',before_knowledge=old_hash)['changes']
        self.assertEqual(changes['added_units'],['rule-2'])
        self.assertNotEqual(changes['before_knowledge'],changes['after_knowledge'])

    def test_source_replacement_removal_and_empty_collection_preserve_results(self):
        case=self.cases[0];done=self.finish(self.start(case),case)
        source=self.project/'replacement';source.mkdir();(source/'source.txt').write_text('Changed source content.',encoding='utf-8')
        replaced=work(project=self.project,input=str(source),collection='Reusable Methods',action='replace')
        changes=work(project=self.project,action='compare')['changes']
        self.assertEqual(changes['changed_sources'],['source.txt'])
        self.assertFalse(changes['knowledge_comparison_available'])
        self.assertEqual(work(project=self.project)['phase'],'extract')
        self.assertTrue(validate_build(done['build'])['valid'])
        work(project=self.project,collection='Reusable Methods',action='remove',remove=['source.txt'])
        self.assertEqual(work(project=self.project,action='inspect')['summary']['source_count'],0)
        self.assertEqual(work(project=self.project)['phase'],'needs_sources')
        self.assertEqual(work(project=self.project,action='compare')['changes']['removed_sources'],['source.txt'])
        self.assertTrue(validate_build(done['build'])['valid'])
        # Re-adding the original material restores its immutable source snapshot.
        restored=work(project=self.project,input=str(ec.ROOT/'fixtures/universal'/case['domain']),collection='Reusable Methods',action='add')
        self.assertEqual(restored['run'],done['run'])
        self.assertEqual(work(project=self.project,action='compare')['changes']['added_sources'],['source.txt'])

    def test_archive_list_summary_restore_and_explicit_use(self):
        case=self.cases[0];self.finish(self.start(case),case)
        work(project=self.project,action='archive',collection='Reusable Methods')
        summary=work(project=self.project,action='list')['collections'][0]
        self.assertTrue(summary['archived']);self.assertEqual(summary['knowledge_units'],2)
        self.assertEqual(summary['goals'],[case['request']])
        self.assertEqual(work(project=self.project)['phase'],'archived_collection')
        self.assertEqual(work(project=self.project,collection='Reusable Methods')['phase'],'complete')
        self.assertFalse(work(project=self.project,action='inspect')['summary']['archived'])
        work(project=self.project,action='archive'); work(project=self.project,action='restore')
        self.assertFalse(work(project=self.project,action='inspect')['summary']['archived'])

    def test_missing_sections_evidence_stale_hash_and_tampering_fail(self):
        case=next(c for c in self.cases if c['intent']=='learn');done=self.finish(self.start(case),case)
        build=Path(done['build']);result=ec.read(build/'result.json');method=ec.read(build/'method.json');ir=ec.validate_ir(done['run'])
        bad=copy.deepcopy(result);bad['sections']=bad['sections'][:1]
        with self.assertRaisesRegex(ec.Invalid,'Missing useful'): validate_outcome(bad,result['brief_id'],ir,method,'learn')
        bad=copy.deepcopy(result);bad['sections'][0]['unit_ids']=[]
        with self.assertRaisesRegex(ec.Invalid,'needs evidence'): validate_outcome(bad,result['brief_id'],ir,method,'learn')
        bad=copy.deepcopy(result);bad['method_hash']='0'*64
        with self.assertRaisesRegex(ec.Invalid,'stale'): validate_outcome(bad,result['brief_id'],ir,method,'learn')
        (build/'result.md').write_text('Pretend result',encoding='utf-8')
        with self.assertRaisesRegex(ec.Invalid,'hash mismatch'): validate_build(build)

    def test_removed_evidence_invalidates_related_units(self):
        from demo import build
        old=build(self.base/'oracle')
        r=work(project=self.project,adopt=str(old),name='Relations',action='save')
        run=Path(r['run']);ir=ec.validate_ir(run)
        related=next(u for u in ir['units'] if u['unit_id']=='herb-daily-opinion')
        sid=related['evidence'][0]['source_id']
        removed=work(project=self.project,collection='Relations',remove=[sid],action='remove')
        changed=ec.read(Path(removed['run'])/'source-change.json')
        self.assertIn('herb-daily-opinion',changed['invalidated_unit_ids'])
        self.assertIn('herb-triage',changed['invalidated_unit_ids'])
        self.assertTrue((Path(removed['run'])/'retained-drafts').exists())
        ec.validate_ir(run)

    def test_named_source_resolution_rejects_missing_and_intent_override(self):
        case=self.cases[0];self.start(case)
        with self.assertRaisesRegex(ec.Invalid,'missing or ambiguous'):
            work(project=self.project,collection='Reusable Methods',action='remove',remove=['missing.txt'])
        with self.assertRaisesRegex(ec.Invalid,'New intent requires'):
            work(project=self.project,target='decide')
        self.assertEqual(work(project=self.project)['phase'],'assess_coverage')

    def test_prepare_collection_extracts_without_goal_result_or_export(self):
        case=self.cases[0]
        r=work(project=self.project,input=str(ec.ROOT/'fixtures/universal'/case['domain']),name='Prepared Knowledge',action='prepare')
        self.assertEqual(r['phase'],'extract');self.seed(r['run'],case)
        self.assertEqual(work(project=self.project,action='prepare')['phase'],'reconcile')
        ready=work(project=self.project,action='prepare',reconciled=True)
        self.assertEqual(ready['phase'],'knowledge_saved')
        self.assertEqual(ready['summary']['knowledge_units'],2)
        self.assertEqual(ready['summary']['goals'],[]);self.assertEqual(ready['summary']['build_count'],0)
        self.assertFalse(any(Path(ready['collection_location']).rglob('SKILL.md')))
        self.assertEqual(work(project=self.project)['phase'],'needs_goal')

    def test_collection_operations_require_real_inputs(self):
        with self.assertRaises(ec.Invalid):work(project=self.project,action='archive')
        with self.assertRaises(ec.Invalid):work(project=self.project,action='compare')
        with self.assertRaises(ec.Invalid):work(project=self.project,action='remove')
        with self.assertRaises(ec.Invalid):work(project=self.project,action='replace')

    def test_evaluation_accepts_general_build_without_export(self):
        from evaluate import prepare_comparison
        case=self.cases[0];done=self.finish(self.start(case),case)
        tasks=[{'case_id':'new-premise','task':'Create an original fictional scene about a library queue.',
                'decision_fields':{'fiction':['yes','no']}}]
        rubric={'expected_decisions':{'new-premise':{'fiction':'yes'}},'human_dimensions':{'quality':'Assess coherence and originality independently.'}}
        ec.write(self.project/'tasks.json',tasks);ec.write(self.project/'rubric.json',rubric)
        output=self.project/'evaluation'
        prepare_comparison(done['run'],done['build'],output,self.project/'tasks.json',self.project/'rubric.json')
        self.assertEqual(ec.read(output/'context.json')['intent'],'create')
        self.assertIn(case['request'],(output/'baseline-prompt.md').read_text(encoding='utf-8'))
        self.assertFalse(any(Path(done['build']).rglob('SKILL.md')))


if __name__=='__main__': unittest.main()
