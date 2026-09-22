"""Authored semantic fixtures exercise generic contracts, not live AI discovery."""
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
from goal_workflow import work, validate_build
from capability_maps import capability_map, CATEGORIES, validate_draft, compare_maps


class CapabilityMapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.project=Path(self.temp.name).resolve()
        self.home=isolate_home(self,self.project)
        self.cases=ec.read(ec.ROOT/'fixtures/opportunities/cases.json')

    def tearDown(self): self.temp.cleanup()

    def seed(self,case):
        source=self.project/'input';source.mkdir(exist_ok=True)
        fixture=ec.ROOT/'fixtures/opportunities'/case['domain']/'source.txt'
        (source/'source.txt').write_bytes(fixture.read_bytes())
        saved=work(project=self.project,input=str(source),name='Test Sources',action='save')
        self.run=Path(saved['run']); self.folder=Path(saved['collection_location'])
        self.checkpoints(case)
        self.task=capability_map(project=self.project,reconciled=True)['agent_task']
        return self.task

    def checkpoints(self,case):
        corpus,docs,_=ec.validate_sources(self.run)
        for doc in docs.values():
            units=[]
            rules=case['rules'] if doc['filename']=='source.txt' else [('claim',doc['segments'][0]['text'])]
            for i,(kind,statement) in enumerate(rules):
                uid=f'rule-{i+1}' if doc['filename']=='source.txt' else 'added-fact'
                seg=next(s for s in doc['segments'] if statement in s['text'])
                units.append({'schema_version':'1.0','unit_id':uid,'type':kind,'status':'explicit',
                    'title':uid,'statement':statement,'scope':'Only the supplied synthetic lesson.',
                    'derivation':'','attribution':[], 'relations':([{'kind':'contradicts','target':'rule-2'}] if case.get('conflicting') and i==0 else []),
                    'evidence':[{'source_id':doc['source_id'],'segment_id':seg['segment_id'],'quote':statement}]})
            ec.write(self.run/'units'/f"{doc['source_id']}.json",{'schema_version':'1.0','corpus_id':corpus['corpus_id'],
                'source_id':doc['source_id'],'note':'Authored complete synthetic checkpoint, not a model extraction result.','units':units})

    def draft(self,case):
        ir=ec.validate_ir(self.run);ids=[u['unit_id'] for u in ir['units'] if u['unit_id']!='added-fact']
        grounding={role:[u['unit_id'] for u in ir['units'] if u['type'] in kinds] for role,kinds in {
            'rules':{'principle','procedure'},'procedures':{'procedure'},'criteria':{'principle'},
            'examples':{'example'},'conditions':{'warning'}}.items()}
        opportunities=[]
        for n,(title,categories) in enumerate([(case['title'],case['categories']),(case['second_title'],case['second_categories'])]):
            opportunities.append({'opportunity_id':f'opportunity-{n+1}','title':title,
                'problem':'Repeated work applying the supplied lesson.','input':case['input'],
                'transformation':'Apply only the selected source statements with their conditions.', 'output':case['output'],
                'categories':categories,'support':'strong','support_reason':'The cited units support this narrowly scoped job.',
                'unit_ids':ids,'grounding':grounding,'boundaries':['Synthetic lesson scope only.'],
                'conflicts':[{'unit_ids':['rule-1','rule-2'],'handling':'Show both thresholds and their different conclusions; do not average them.'}] if case.get('conflicting') else [],
                **{key:{'level':'medium','reason':'Reusable on another task within the same narrow scope.'} for key in ['reuse','actionability','judgment','saved_work']},
                'beyond_qa':{'verdict':'modest' if case['domain']=='reference' else 'distinct','reason':'Saved method and evidence can be reused; effectiveness has not been measured.'},
                'targets':[{'label':'Reusable guide','delivery':'text','description':'Saved instructions with evidence and limits.'}],
                'ranking_reason':'Source support first; other qualitative factors are tied in this fixture.'})
        return {'schema_version':'1.0','binding_hash':self.task['binding_hash'],
            'category_assessments':[{'category':cat,'reason':'Authored assessment; only listed jobs are supported in this fixture.','unit_ids':ids} for cat in CATEGORIES],
            'opportunities':opportunities,'no_opportunities_reason':'',
            'semantic_review':{'status':'assistant-reviewed','limitations':'Authored test oracle; not live semantic evaluation.'}}

    def save(self,draft):
        path=self.project/'draft.json';ec.write(path,draft)
        return capability_map(project=self.project,draft=str(path))['map']

    def test_unrelated_domains_same_discovery_and_multiple_categories(self):
        for case in self.cases:
            with self.subTest(domain=case['domain']), tempfile.TemporaryDirectory() as root:
                self.project=Path(root).resolve();self.home=isolate_home(self,self.project)
                self.seed(case);record=self.save(self.draft(case))
                self.assertEqual(len(record['recommended_ids']),2)
                self.assertEqual({c for o in record['draft']['opportunities'] for c in o['categories']},set(case['categories']+case['second_categories']))
                self.assertEqual(record['source_coverage']['opportunity-1'],[next(iter(ec.validate_sources(self.run)[1]))])

    def test_procedural_do_review(self):
        case=self.cases[0];self.seed(case);record=self.save(self.draft(case))
        self.assertIn('do',record['draft']['opportunities'][0]['categories'])
        self.assertIn('review',record['draft']['opportunities'][1]['categories'])

    def test_facts_do_not_support_flashy_procedural_agents(self):
        case=self.cases[4];self.seed(case);draft=self.draft(case)
        for category in ['do','review','decide','automate','evaluate']:
            bad=copy.deepcopy(draft);bad['opportunities'][0]['title']='Autonomous Expert Agent'
            bad['opportunities'][0]['categories']=[category]
            with self.assertRaises(ec.Invalid): self.save(bad)
        self.assertEqual(len(self.save(draft)['recommended_ids']),2)

    def test_disagreements_required_in_decision_and_evaluation(self):
        case=self.cases[5];self.seed(case);draft=self.draft(case)
        bad=copy.deepcopy(draft);bad['opportunities'][1]['conflicts']=[]
        with self.assertRaisesRegex(ec.Invalid,'disagreement'): self.save(bad)
        record=self.save(draft)
        self.assertEqual(len(record['draft']['opportunities'][1]['conflicts']),1)

    def test_no_fake_confidence_or_unknown_metadata(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case)
        draft['opportunities'][0]['confidence']=0.99
        with self.assertRaises(ec.Invalid): self.save(draft)

    def test_input_transformation_output_required_and_duplicate_ids_rejected(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case)
        for field in ['input','transformation','output']:
            bad=copy.deepcopy(draft);bad['opportunities'][0][field]=''
            with self.assertRaises(ec.Invalid): self.save(bad)
        draft['opportunities'][1]['opportunity_id']='opportunity-1'
        with self.assertRaisesRegex(ec.Invalid,'Duplicate'): self.save(draft)

    def test_reload_fresh_process_and_immutable_ir(self):
        case=self.cases[0];self.seed(case);original=(self.run/'ir.json').read_bytes()
        record=self.save(self.draft(case))
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(ec.ROOT/'scripts/ec.py'),'map','--project',str(self.project),
            '--collection','Test Sources','--action','inspect'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout)['map'],record)
        self.assertEqual((self.run/'ir.json').read_bytes(),original)
        self.assertNotIn('opportunities',ec.validate_ir(self.run))

    def test_source_addition_new_map_old_inspectable_and_selection_stale(self):
        case=self.cases[0];self.seed(case);old=self.save(self.draft(case))
        original=(self.folder/'maps'/f"{old['map_id']}.json").read_bytes()
        extra=self.project/'extra';extra.mkdir();(extra/'extra.txt').write_text('A new factual note.',encoding='utf-8')
        changed=work(project=self.project,collection='Test Sources',action='add',input=str(extra));self.run=Path(changed['run'])
        with self.assertRaisesRegex(ec.Invalid,'stale'): capability_map(project=self.project,action='select',select='2')
        self.checkpoints(case);self.task=capability_map(project=self.project,reconciled=True)['agent_task']
        new=self.save(self.draft(case))
        self.assertNotEqual(old['map_id'],new['map_id'])
        self.assertEqual(original,(self.folder/'maps'/f"{old['map_id']}.json").read_bytes())
        self.assertEqual(capability_map(project=self.project,action='inspect',map_id=old['map_id'])['map'],old)
        diff=capability_map(project=self.project,action='compare',before=old['map_id'],map_id=new['map_id'])
        self.assertIn('unchanged',diff['changes'])

    def test_same_ir_regeneration_preserves_old_map_and_last_shown_selection(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case);old=self.save(draft)
        task=capability_map(project=self.project,regenerate=True)
        self.assertEqual(task['phase'],'discover_opportunities')
        draft['opportunities'][1]['reuse']['level']='high';new=self.save(draft)
        self.assertEqual(new['recommended_ids'][0],'opportunity-2')
        capability_map(project=self.project,action='inspect',map_id=old['map_id'])
        selected=capability_map(project=self.project,action='select',select='2')
        self.assertEqual(selected['selected_opportunity'],'opportunity-2')
        self.assertEqual(selected['selected_map'],old['map_id'])

    def test_weak_opportunities_are_gaps_not_builds(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case)
        draft['opportunities'][0]['support']='weak';record=self.save(draft)
        self.assertEqual(record['recommended_ids'],['opportunity-2'])
        with self.assertRaises(ec.Invalid): capability_map(project=self.project,action='select',select='opportunity-1')

    def test_no_opportunity_is_valid_and_all_categories_assessed(self):
        case=self.cases[4];self.seed(case);draft=self.draft(case);draft['opportunities']=[]
        draft['no_opportunities_reason']='Nothing reusable beyond these isolated facts for the assessed scope.'
        self.assertEqual(self.save(draft)['recommended_ids'],[])
        draft['category_assessments'][0]['category']='reference'
        with self.assertRaises(ec.Invalid): self.save(draft)

    def test_grounding_unknown_refs_and_future_only_targets_rejected(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case)
        bad=copy.deepcopy(draft);bad['opportunities'][0]['grounding']['rules']=['absent']
        with self.assertRaises(ec.Invalid): self.save(bad)
        bad=copy.deepcopy(draft);bad['opportunities'][0]['targets'][0]['delivery']='future'
        with self.assertRaises(ec.Invalid): self.save(bad)
        bad=copy.deepcopy(draft);bad['opportunities'][0]['grounding']['examples']=[]
        with self.assertRaises(ec.Invalid): self.save(bad)

    def test_compare_strength_gaps_conflicts_and_removals(self):
        case=self.cases[0];self.seed(case);old=self.save(self.draft(case));new=copy.deepcopy(old)
        old['draft']['opportunities'][0]['support']='weak'
        new['draft']['opportunities'][0]['conflicts']=[{'unit_ids':['rule-1','rule-2'],'handling':'Preserve disagreement.'}]
        new['draft']['opportunities'].pop()
        diff=compare_maps(old,new)
        self.assertEqual(diff['newly_supported'],['opportunity-1'])
        self.assertEqual(diff['affected_by_contradictions'],['opportunity-1'])
        self.assertEqual(diff['removed_or_invalidated'],['opportunity-2'])

    def test_select_flows_to_complete_build_without_asset_type_or_application_input(self):
        case=self.cases[0];self.seed(case);record=self.save(self.draft(case))
        selected=capability_map(project=self.project,action='select',select=case['second_title'])
        self.assertEqual(selected['phase'],'assess_coverage')
        task=selected['agent_task'];draft=Path(task['draft']);brief=ec.read(task['brief'])
        self.assertEqual(brief['intent'],'create')
        self.assertEqual(json.loads(brief['context'])['opportunity']['categories'],['review','improve'])
        self.assertEqual(json.loads(brief['context'])['capability_map'],record['map_id'])
        # Complete the existing build coordinator with an authored method/result oracle.
        ir=ec.validate_ir(self.run);ids=[u['unit_id'] for u in ir['units']]
        ec.write(draft/'coverage.json',{'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
            'decision':'reuse','source_ids':[],'reason':'Selected units suffice for the synthetic method.','unsupported':[]})
        cap={'schema_version':'1.0','capability_id':'portrait-critic','title':case['second_title'],
            'description':'Review focus and motion blur.','rationale':'Apply the selected source checks.',
            'inputs':case['input'],'output_contract':case['output'],'unit_ids':ids,
            'steps':[{'instruction':u['statement'],'unit_ids':[u['unit_id']]} for u in ir['units']],
            'boundaries':['Synthetic lesson scope only.'],'conflict_policy':'Preserve disagreements.',
            'checks':['Separate focus from motion blur.'],
            'examples':[{'input':'Eyes soft, background sharp.','output':'Check focus placement first.','unit_ids':ids,'status':'synthetic'}]}
        method={'schema_version':'1.0','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],'capability':cap}
        ec.write(draft/'method.json',method)
        self.assertEqual(work(project=self.project)['phase'],'apply_method')
        ec.write(draft/'result.json',{'schema_version':'1.1','brief_id':task['brief_id'],'ir_hash':task['ir_hash'],
            'method_hash':ec.fingerprint(method),'target':'create','summary':'Reusable portrait critique method.',
            'sections':[{'kind':'deliverable','title':'Portrait Critic','content':'Supply a portrait and settings. Check focus first; then isolate motion. Report a retake plan. Example: sharp background and soft eyes warrants checking focus placement.',
                         'unit_ids':ids,'status':'original'}], 'disagreements':[],
            'limitations':['No lighting or composition diagnosis.'],'unsupported':[],'additional_general_advice':[]})
        done=work(project=self.project,reviewed=True)
        self.assertEqual(done['phase'],'complete');self.assertTrue(validate_build(done['build'])['valid'])
        self.assertFalse((Path(done['build'])/'SKILL.md').exists())

    def test_draft_resume_stale_binding_and_historical_tampering(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case)
        ec.write(self.task['draft'],draft)
        record=capability_map(project=self.project)['map']
        self.assertEqual(capability_map(project=self.project)['map'],record)
        bad=copy.deepcopy(draft);bad['binding_hash']='0'*64
        with self.assertRaisesRegex(ec.Invalid,'stale'): self.save(bad)
        record['draft']['opportunities'][0]['title']='Tampered title'
        ec.write(self.folder/'maps'/f"{record['map_id']}.json",record)
        with self.assertRaisesRegex(ec.Invalid,'hash/identity'): capability_map(project=self.project,action='inspect')

    def test_source_removal_never_silently_reuses_old_map(self):
        case=self.cases[0];self.seed(case);old=self.save(self.draft(case))
        work(project=self.project,collection='Test Sources',action='remove',remove=['source.txt'])
        self.assertEqual(capability_map(project=self.project)['phase'],'needs_sources')
        self.assertEqual(capability_map(project=self.project,action='inspect',map_id=old['map_id'])['map'],old)
        with self.assertRaisesRegex(ec.Invalid,'stale'): capability_map(project=self.project,action='select',select='1')

    def test_rank_prioritizes_support_before_novelty_or_reuse(self):
        case=self.cases[0];self.seed(case);draft=self.draft(case)
        draft['opportunities'][0]['support']='supported'
        draft['opportunities'][0]['reuse']['level']='high'
        self.assertEqual(self.save(draft)['recommended_ids'],['opportunity-2','opportunity-1'])

    def test_malformed_map_index_rejected(self):
        case=self.cases[0];self.seed(case);record=self.save(self.draft(case))
        ec.write(self.folder/'maps/index.json',{'maps':[record['map_id'],record['map_id']],'last_shown':record['map_id']})
        with self.assertRaisesRegex(ec.Invalid,'Malformed map history'): capability_map(project=self.project,action='list')

    def test_opposing_evidence_outside_selection_still_requires_conflict(self):
        case=self.cases[5];self.seed(case);draft=self.draft(case)
        o=draft['opportunities'][0];o['unit_ids'].remove('rule-2')
        for refs in o['grounding'].values():
            if 'rule-2' in refs: refs.remove('rule-2')
        self.save(draft)
        o['conflicts']=[]
        with self.assertRaisesRegex(ec.Invalid,'disagreement'): self.save(draft)


if __name__=='__main__': unittest.main()
