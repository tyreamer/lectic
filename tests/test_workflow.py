"""State-machine/installation tests with authored oracle data, not live model evals."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ec
from demo import build
from evaluate import score
from ingestors import adapter_for
from ingestors.youtube import YouTubeIngestor
from install_skill import install
from workflow import compile_workflow, summary


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / 'User Project With Spaces'
        self.project.mkdir()
        self.oracle = None

    def tearDown(self):
        self.temp.cleanup()

    def seed(self, run):
        """Import authored fixture checkpoints at the boundary where a real agent reasons."""
        if self.oracle is None: self.oracle = build(self.base / 'authored-oracle')
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_name = {d['filename']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_name[doc['filename']]
            self.assertEqual(original['content_hash'], doc['content_hash'])
            part = ec.read(self.oracle / f'units/{original["source_id"]}.json')
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def start(self, domain=None):
        source = ec.ROOT / ('fixtures/' + domain if domain else 'fixtures/transcripts')
        result = compile_workflow(str(source), project=self.project)
        self.assertEqual(result['phase'], 'extract')
        return Path(result['run'])

    def discover(self, domain=None):
        run = self.start(domain)
        self.seed(run)
        self.assertEqual(compile_workflow(project=self.project)['phase'], 'reconcile')
        result = compile_workflow(project=self.project, reconciled=True)
        self.assertEqual(result['phase'], 'discover')
        ir = ec.validate_ir(run)
        ids = {u['unit_id'] for u in ir['units']}
        caps = [c for c in ec.read(ec.ROOT / 'fixtures/demo_capabilities.json') if set(c['unit_ids']) <= ids]
        ec.write(run / 'capabilities.json', {'schema_version':'1.0', 'ir_hash':ec.fingerprint(ir), 'capabilities':caps})
        result = compile_workflow(project=self.project, intent='discover')
        self.assertEqual(result['phase'], 'choose')
        return run, result

    def test_installed_skill_runs_from_separate_project_with_spaces(self):
        installed = install(self.base / 'Personal Skills With Spaces/expertise-compiler')
        shutil.copytree(ec.ROOT / 'fixtures/photography', self.project / 'input')
        before = {p.relative_to(installed).as_posix() for p in installed.rglob('*') if p.is_file()}
        command = [sys.executable, '-B', str(installed / 'scripts/ec.py'), 'compile', './input']
        result = subprocess.run(command, cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['phase'], 'extract')
        self.assertTrue(Path(payload['run']).is_relative_to(self.project))
        self.assertTrue((self.project / '.expertise-compiler/session.json').is_file())
        self.assertFalse((installed / '.expertise-compiler').exists())
        self.assertEqual(before, {p.relative_to(installed).as_posix() for p in installed.rglob('*') if p.is_file()})
        self.assertNotIn('.git/config', before)
        self.assertFalse(any(p.startswith('workspace/') for p in before))
        # Continue the installed entry point through its semantic boundaries too.
        run = Path(payload['run'])
        self.seed(run)
        cli = [sys.executable, '-B', str(installed / 'scripts/ec.py'), 'compile']
        def invoke(*args):
            completed = subprocess.run(cli + list(args), cwd=self.project, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(completed.stdout)
        self.assertEqual(invoke()['phase'], 'reconcile')
        self.assertEqual(invoke('--reconciled')['phase'], 'discover')
        ir = ec.validate_ir(run)
        cap = next(c for c in ec.read(ec.ROOT / 'fixtures/demo_capabilities.json') if c['capability_id'] == 'handheld-blur-reviewer')
        ec.write(run / 'capabilities.json', {'schema_version':'1.0', 'ir_hash':ec.fingerprint(ir), 'capabilities':[cap]})
        ready = invoke('--intent', 'build', '--select', 'handheld-blur-reviewer')
        self.assertEqual(ready['phase'], 'ready')
        self.assertEqual(invoke('--intent', 'use')['built'], ready['built'])
        result = invoke('--intent', 'compare', '--tasks', str(installed / 'fixtures/flows/photography-tasks.json'), '--rubric', str(installed / 'fixtures/flows/photography-rubric.json'))
        self.assertEqual(result['phase'], 'evaluate')
        self.assertEqual(install(installed), installed)

    def test_two_domains_compile_discover_build_use_compare(self):
        for flow in ec.read(ec.ROOT / 'fixtures/flows/conversations.json'):
            with self.subTest(domain=flow['domain']):
                run, choices = self.discover(flow['domain'])
                self.assertEqual(choices['summary']['capabilities'][0]['id'], flow['capability_id'])
                self.assertEqual(choices['summary']['capabilities'][0]['supporting_sources'], 1)
                built = compile_workflow(project=self.project, intent='build', select='1')
                self.assertEqual(built['phase'], 'ready')
                package = Path(built['built'][0]['location'])
                ec.validate_package(package)
                used = compile_workflow(project=self.project, intent='use')
                self.assertEqual(used['phase'], 'use')
                self.assertEqual(used['built'][0]['location'], str(package))
                preparation = compile_workflow(project=self.project, intent='compare')
                self.assertEqual(preparation['phase'], 'prepare_evaluation')
                comparison = compile_workflow(project=self.project, intent='compare', tasks=str(ec.ROOT / flow['tasks']), rubric=str(ec.ROOT / flow['rubric']))
                self.assertEqual(comparison['phase'], 'evaluate')
                evaluation = Path(comparison['evaluation'])
                baseline = (evaluation / 'baseline-prompt.md').read_text(encoding='utf-8')
                compiled = (evaluation / 'compiled-prompt.md').read_text(encoding='utf-8')
                self.assertNotIn('expected_decisions', baseline + compiled)
                tasks = ec.read(evaluation / 'tasks.json')
                for task in tasks:
                    self.assertIn(task['task'], baseline)
                    self.assertIn(task['task'], compiled)
                self.assertFalse(any('rubric' in p.name for p in package.rglob('*')))
                # Feed explicitly synthetic responses to exercise checker plumbing only.
                expected = ec.read(evaluation / 'rubric.json')['expected_decisions']
                unit = ec.read(package / 'references/knowledge.json')[0]
                evidence = unit['evidence'][0]
                _, docs, _ = ec.validate_sources(run)
                citation = {'unit_id':unit['unit_id'], 'filename':docs[evidence['source_id']]['filename'], 'quote':evidence['quote']}
                responses = [{'case_id':t['case_id'], 'answer':'Synthetic checker fixture, not a model answer.',
                              'decisions':expected[t['case_id']], 'citations':[citation]} for t in tasks]
                ec.write(evaluation / 'responses.json', responses)
                report = score(run, evaluation / 'responses.json', 'compiled', evaluation)
                self.assertEqual(report['decision_matches'], 6)
                self.assertEqual(report['citation_error_count'], 0)
                self.assertFalse(report['quality_win_established'])

    def test_build_all_needs_no_selection_and_preserves_conflicts(self):
        _, options = self.discover()
        self.assertEqual(options['summary']['disagreements'], 1)
        result = compile_workflow(project=self.project, intent='build', build_all=True)
        self.assertEqual(result['phase'], 'ready')
        self.assertEqual(len(result['built']), 3)
        herb = next(b for b in result['built'] if b['id'] == 'container-herb-reviewer')
        self.assertIn('Noah', herb['disagreements'])

    def test_proposal_numbers_do_not_silently_change_meaning(self):
        run, _ = self.discover()
        caps = ec.read(run / 'capabilities.json')
        caps['capabilities'].reverse()
        ec.write(run / 'capabilities.json', caps)
        result = compile_workflow(project=self.project, intent='build', select='2')
        self.assertEqual(result['phase'], 'choose')
        self.assertNotIn('built', result)
        result = compile_workflow(project=self.project, intent='build', select='2')
        self.assertEqual(result['built'][0]['id'], caps['capabilities'][1]['capability_id'])

    def test_checkpoint_change_invalidates_review_and_capabilities(self):
        run, _ = self.discover('photography')
        part = next((run / 'units').glob('*.json'))
        data = ec.read(part); data['units'][0]['statement'] += ' Rephrased for clarity.'; ec.write(part, data)
        result = compile_workflow(project=self.project, intent='build', select='handheld-blur-reviewer')
        self.assertEqual(result['phase'], 'reconcile')
        result = compile_workflow(project=self.project, reconciled=True, intent='build', select='handheld-blur-reviewer')
        self.assertEqual(result['phase'], 'discover')
        self.assertIn('stale', result['agent_task']['reason'])

    def test_interruption_keeps_valid_checkpoints_and_repairs_invalid_ones(self):
        run = self.start()
        self.seed(run)
        paths = sorted((run / 'units').glob('*.json'))
        retained = paths[0].read_bytes()
        paths[1].unlink()
        bad = ec.read(paths[2]); bad['units'][0]['evidence'][0]['quote'] = 'An invented quotation.'; ec.write(paths[2], bad)
        result = compile_workflow(project=self.project)
        self.assertEqual(result['phase'], 'extract')
        self.assertEqual(len(result['agent_task']['pending_sources']), 2)
        self.assertEqual(len(result['agent_task']['repairs']), 1)
        self.assertEqual(paths[0].read_bytes(), retained)

    def test_changed_input_creates_new_snapshot(self):
        inputs = self.project / 'input'; inputs.mkdir()
        (inputs / 'a.txt').write_text('Speaker: Original transcript.', encoding='utf-8')
        first = compile_workflow('input', project=self.project)
        self.assertEqual(first['summary']['caption_coverage_seconds'], None)
        (inputs / 'a.txt').write_text('Speaker: A revised transcript.', encoding='utf-8')
        second = compile_workflow('input', project=self.project)
        self.assertNotEqual(first['run'], second['run'])
        ec.validate_sources(first['run']); ec.validate_sources(second['run'])
        self.assertEqual(compile_workflow(project=self.project)['run'], second['run'])

    def test_empty_extraction_explains_no_supported_knowledge(self):
        run = self.start('photography')
        corpus, docs, _ = ec.validate_sources(run)
        for sid in docs:
            ec.write(run / f'units/{sid}.json', {'schema_version':'1.0','corpus_id':corpus['corpus_id'],'source_id':sid,
                                               'note':'Test-only empty extraction with a reason.', 'units':[]})
        result = compile_workflow(project=self.project, intent='build', build_all=True)
        self.assertEqual(result['phase'], 'no_supported_knowledge')
        self.assertNotIn('built', result)

    def test_negative_discovery_assessment_blocks_old_plans(self):
        run, _ = self.discover('photography')
        ir = ec.validate_ir(run)
        ec.write(run / 'discovery-assessment.json', {'schema_version':'1.0', 'ir_hash':ec.fingerprint(ir),
                 'no_capability_reason':'The requested commercial pricing goal is not supported.',
                 'weakly_supported':[{'topic':'Commercial pricing','reason':'No pricing methods are provided.','unit_ids':[]}]})
        result = compile_workflow(project=self.project, intent='build', select='handheld-blur-reviewer')
        self.assertEqual(result['phase'], 'no_supported_capabilities')
        self.assertNotIn('built', result)

    def test_changed_package_plan_creates_separate_export(self):
        run, _ = self.discover('photography')
        first = compile_workflow(project=self.project, intent='build', select='handheld-blur-reviewer')['built'][0]['location']
        caps = ec.read(run / 'capabilities.json')
        caps['capabilities'][0]['boundaries'].append('Additional explicit scope clarification.')
        ec.write(run / 'capabilities.json', caps)
        second = compile_workflow(project=self.project, intent='build', select='handheld-blur-reviewer')['built'][0]['location']
        self.assertNotEqual(first, second)
        ec.validate_package(first); ec.validate_package(second)

    def test_caption_overlap_is_not_double_counted(self):
        doc = {'segments':[{'start':1, 'end':5},{'start':3, 'end':8},{'start':12, 'end':13}]}
        result = summary({'one':doc, 'two':{'segments':[{'start':None,'end':None}]}})
        self.assertEqual(result['caption_coverage_seconds'], 8)
        self.assertEqual(result['sources_with_timed_captions'], 1)
        self.assertFalse(result['recording_duration_known'])

    def test_youtube_boundary_is_optional_and_offline(self):
        with patch('ingestors.youtube.shutil.which', return_value=None):
            for url in ['youtube.com/watch?v=o64cI6tebnU', 'https://youtu.be/o64cI6tebnU']:
                self.assertIsInstance(adapter_for(url), YouTubeIngestor)
                with self.assertRaisesRegex(ec.Invalid, 'yt-dlp is not installed'):
                    compile_workflow(url, project=self.project)
        self.assertFalse(YouTubeIngestor.accepts('https://youtube.com.evil.example/watch?v=abc'))
        self.assertFalse((self.project / '.expertise-compiler').exists())

    def test_installer_refuses_to_overwrite_existing_edits(self):
        destination = install(self.base / 'installed/expertise-compiler')
        (destination / 'README.md').write_text('User edits', encoding='utf-8')
        with self.assertRaisesRegex(ec.Invalid, 'differs'): install(destination)
        self.assertEqual((destination / 'README.md').read_text(encoding='utf-8'), 'User edits')

    def test_evaluation_rubric_is_frozen_and_leaks_are_rejected(self):
        run, _ = self.discover('photography')
        result = compile_workflow(project=self.project, intent='compare', tasks=str(ec.ROOT / 'fixtures/flows/photography-tasks.json'), rubric=str(ec.ROOT / 'fixtures/flows/photography-rubric.json'))
        evaluation = Path(result['evaluation'])
        rubric = ec.read(evaluation / 'rubric.json')
        rubric['expected_decisions']['sharp-wrong-plane']['shutter_is_established_fix'] = 'yes'
        ec.write(evaluation / 'rubric.json', rubric)
        with self.assertRaisesRegex(ec.Invalid, 'changed after preparation'):
            score(run, evaluation / 'response-template.json', 'compiled', evaluation)

    def test_cli_resume_adopts_legacy_run(self):
        run = build(self.project / 'legacy-demo')
        result = subprocess.run([sys.executable, str(ec.ROOT / 'scripts/ec.py'), 'compile', '--project', str(self.project), '--run', str(run)], cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['phase'], 'reconcile')

    def test_new_session_asks_for_content_not_commands(self):
        result = compile_workflow(project=self.project)
        self.assertEqual(result['phase'], 'needs_input')
        self.assertFalse((self.project / '.expertise-compiler/session.json').exists())

    def test_build_intent_survives_interruption_without_reselection(self):
        start = compile_workflow(str(ec.ROOT / 'fixtures/transcripts'), project=self.project, intent='build', build_all=True)
        run = Path(start['run'])
        self.seed(run)
        self.assertEqual(compile_workflow(project=self.project)['phase'], 'reconcile')
        self.assertEqual(compile_workflow(project=self.project, reconciled=True)['phase'], 'discover')
        ir = ec.validate_ir(run)
        ec.write(run / 'capabilities.json', {'schema_version':'1.0','ir_hash':ec.fingerprint(ir),
                                           'capabilities':ec.read(ec.ROOT / 'fixtures/demo_capabilities.json')})
        result = compile_workflow(project=self.project)
        self.assertEqual(result['phase'], 'ready')
        self.assertEqual(len(result['built']), 3)

    def test_malformed_session_fails_with_a_validation_error(self):
        run = self.start('photography')
        path = self.project / '.expertise-compiler/session.json'
        session = ec.read(path); session['last_built'] = []; ec.write(path, session)
        with self.assertRaises(ec.Invalid): compile_workflow(project=self.project)
        ec.validate_sources(run)


if __name__ == '__main__':
    unittest.main()
