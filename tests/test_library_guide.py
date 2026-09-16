"""Saved-state and guidance contracts. Suggestion prose is an authored oracle."""
import copy
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ec
import test_capability_maps
import test_goals
from capture_store import CaptureStore
from capture_write import save_capture
from collection_store import Library
from goal_workflow import work, validate_build
from library_guide import library_view, use_guide, validate_guide


class LibraryGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / 'Project'
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        helper = test_goals.GoalTests()
        helper.base, helper.project, helper.oracle = self.base, self.project, None
        return helper.finish(helper.start())

    def mapped(self, domain='photography'):
        helper = test_capability_maps.CapabilityMapTests()
        helper.project = self.project
        case = next(c for c in ec.read(ec.ROOT / 'fixtures/opportunities/cases.json') if c['domain'] == domain)
        helper.seed(case)
        helper.save(helper.draft(case))
        return helper

    def draft(self, view=None, context=False):
        view = view or library_view(self.project)
        refs = [r for r in view['references'].values() if r['status'] in {'ready', 'can_build'}][:3]
        cards = [{'card_id': f'use-{i}', 'reference': ref['reference'],
            'availability': 'build_first' if ref['kind'] == 'opportunity' else 'ready',
            'title': ref['title'], 'input': ref['input'], 'output': ref['output'],
            'why_useful': 'Apply these saved criteria to a new task without reconstructing the method.',
            'try_prompt': 'Use ' + ref['title'] + ' on this draft.', 'limits': ref['boundaries'],
            'unit_ids': ref['unit_ids'], 'context_ids': ['role'] if context else []}
            for i, ref in enumerate(refs)]
        return {'schema_version': '1.0', 'binding_hash': view['binding_hash'],
            'saved_summary': 'The listed material and methods are saved in this project.',
            'context': [{'context_id':'role','text':'I make game review videos.','origin':'user_message',
                'source':'User message in this test session.','status':'provided'}] if context else [],
            'cards': cards, 'recommended_card': cards[0]['card_id'] if cards else '',
            'recommendation_reason':'Start with the current, source-supported application.',
            'question':'', 'no_suggestions_reason':'No method or supported opportunity is available.' if not cards else '',
            'semantic_review':'assistant-reviewed'}

    def save(self, draft):
        path = self.project / 'guide-draft.json'
        ec.write(path, draft)
        return use_guide(project=self.project, action='save', draft=str(path))

    def hashes(self):
        return {p.relative_to(self.project).as_posix(): ec.digest(p.read_bytes())
                for p in self.project.rglob('*') if p.is_file()}

    def test_empty_library_reads_without_creating_state(self):
        before = self.hashes()
        view = library_view(self.project)
        self.assertEqual(view['collections'], [])
        self.assertIn('Other projects', view['markdown'])
        self.assertEqual(before, self.hashes())
        saved = self.save(self.draft(view))
        self.assertEqual(saved['guide']['cards'], [])

    def test_saved_sources_are_not_presented_as_ready(self):
        work(project=self.project, input=str(ec.ROOT / 'fixtures/debugging'), name='Saved Only', action='save')
        view = library_view(self.project)
        self.assertEqual(view['collections'][0]['knowledge_status'], 'sources_saved')
        self.assertEqual(view['references'], {})
        self.assertNotIn('Ready to use', view['markdown'])

    def test_ready_method_and_previous_result_are_real_and_read_only(self):
        done = self.build()
        before = self.hashes()
        view = library_view(self.project)
        ref = next(iter(view['references'].values()))
        self.assertEqual(ref['status'], 'ready')
        self.assertEqual(ref['result'], done['result'])
        self.assertTrue(Path(ref['method']).is_file())
        self.assertEqual(ref['validation']['effectiveness_testing'], 'not-run')
        self.assertEqual(before, self.hashes())
        self.assertTrue(done['guidance'].endswith('guide-use.md'))

    def test_archived_collection_remains_archived_when_browsed(self):
        self.build()
        work(project=self.project, collection='My Methods', action='archive')
        before = self.hashes()
        self.assertTrue(library_view(self.project)['collections'][0]['archived'])
        self.assertEqual(before, self.hashes())

    def test_source_update_preserves_old_result_but_marks_method_historical(self):
        done = self.build()
        original = Path(done['result']).read_bytes()
        added = self.base / 'added'; added.mkdir()
        (added / 'lesson.txt').write_text('A newly supplied observation.', encoding='utf-8')
        work(project=self.project, collection='My Methods', input=str(added), action='add')
        view = library_view(self.project)
        self.assertEqual(next(iter(view['references'].values()))['status'], 'saved_version')
        self.assertEqual(original, Path(done['result']).read_bytes())
        self.assertTrue(validate_build(done['build'])['valid'])

    def test_corrupt_build_is_reported_and_never_ready(self):
        done = self.build()
        Path(done['result']).write_text('Changed output.', encoding='utf-8')
        view = library_view(self.project)
        self.assertEqual(view['references'], {})
        self.assertTrue(view['collections'][0]['issues'])

    def test_capture_url_availability_visible_without_compilation(self):
        inbox = self.base / 'Drop'
        save_capture(inbox, url='https://example.com/talk', note='Not company policy.')
        CaptureStore(self.project).import_folder(inbox)
        view = library_view(self.project)
        capture = view['collections'][0]['captures'][0]
        self.assertEqual(capture['processing_status'], 'awaiting_retrieval')
        self.assertEqual(capture['user_context'][0]['note'], 'Not company policy.')
        self.assertEqual(view['references'], {})

    def test_guide_reload_and_direct_method_use_without_source_upload(self):
        done = self.build()
        saved = self.save(self.draft())
        result = subprocess.run([sys.executable, '-B', str(ec.ROOT / 'scripts/ec.py'), 'guide',
            '--project', str(self.project), '--action', 'show'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['guide_id'], saved['guide_id'])
        selected = use_guide(project=self.project, action='select', select='1')
        self.assertEqual(selected['phase'], 'use_saved_method')
        self.assertEqual(selected['saved_method']['method'], done['method'])
        self.assertEqual(selected['selected_use']['title'], saved['guide']['cards'][0]['title'])

    def test_opportunity_is_not_built_until_selected(self):
        self.mapped()
        saved = self.save(self.draft(context=True))
        self.assertEqual(Library(self.project).resolve()[1]['builds'], [])
        result = use_guide(project=self.project, action='select', select=1)
        self.assertEqual(result['phase'], 'assess_coverage')
        self.assertEqual(result['selected_opportunity'], 'opportunity-1')
        brief = ec.read(result['agent_task']['brief'])
        self.assertIn(saved['guide_id'], brief['context'])
        self.assertIn('I make game review videos.', brief['context'])
        self.assertNotIn('I make game review videos.', json.dumps(ec.validate_ir(result['run'])))

    def test_invalid_references_readiness_personalization_and_confidence_rejected(self):
        self.mapped()
        view = library_view(self.project)
        original = self.draft(view)
        for mutation in [{'reference':'made-up'}, {'availability':'ready'},
                         {'unit_ids':['missing']}, {'context_ids':['invented-memory']}, {'confidence':0.99}]:
            bad = copy.deepcopy(original); bad['cards'][0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ec.Invalid): validate_guide(bad, view)

    def test_personal_context_is_private_not_ir_or_export(self):
        done = self.build()
        folder, data = Library(self.project).resolve()
        run = Library.run(folder, data)
        original = (run / 'ir.json').read_bytes()
        saved = self.save(self.draft(context=True))
        self.assertEqual(saved['guide']['context'][0]['origin'], 'user_message')
        self.assertEqual((run / 'ir.json').read_bytes(), original)
        exported = work(project=self.project, collection='My Methods', action='export')
        for path in Path(exported['skill']).parent.rglob('*'):
            if path.is_file(): self.assertNotIn(b'I make game review videos.', path.read_bytes())
        self.assertTrue(validate_build(done['build'])['valid'])

    def test_corrected_context_creates_new_guide_preserving_old(self):
        self.build()
        draft = self.draft(context=True)
        first = self.save(draft)
        draft['context'][0]['text'] = 'I now make hardware reviews.'
        second = self.save(draft)
        self.assertNotEqual(first['guide_id'], second['guide_id'])
        shown = use_guide(project=self.project, action='show', guide_id=first['guide_id'])
        self.assertEqual(shown['guide']['context'][0]['text'], 'I make game review videos.')

    def test_stale_guide_selection_rejected_after_source_update(self):
        self.build(); saved = self.save(self.draft())
        added = self.base / 'added'; added.mkdir()
        (added / 'lesson.txt').write_text('A new observation.', encoding='utf-8')
        work(project=self.project, collection='My Methods', input=str(added), action='add')
        shown = use_guide(project=self.project, action='show', guide_id=saved['guide_id'])
        self.assertTrue(shown['stale'])
        with self.assertRaisesRegex(ec.Invalid, 'stale'):
            use_guide(project=self.project, action='select', select='1')

    def test_three_domains_use_same_library_and_guide_logic(self):
        for case in ec.read(ec.ROOT / 'fixtures/use-guidance/cases.json')['cases']:
            domain = case['domain']
            with self.subTest(domain=domain):
                self.project = self.base / domain; self.project.mkdir()
                self.mapped(domain)
                view = library_view(self.project)
                draft = self.draft(view)
                originals = draft['cards']
                draft['context'] = case['context']
                draft['cards'] = [{**originals[use['opportunity']],
                    **{k:v for k,v in use.items() if k != 'opportunity'}, 'card_id':f'use-{i}'}
                    for i,use in enumerate(case['uses'])]
                saved = self.save(draft)
                self.assertEqual(len(saved['guide']['cards']), len(case['uses']))
                self.assertTrue(all(c['availability'] == 'build_first' for c in saved['guide']['cards']))
                self.assertIn('**Try saying:**', saved['markdown'])
                self.assertEqual(view['binding_hash'], library_view(self.project)['binding_hash'])

    def test_saved_guide_numbers_survive_another_map_display(self):
        self.mapped()
        draft = self.draft()
        draft['cards'].reverse()
        saved = self.save(draft)
        from capability_maps import capability_map
        capability_map(project=self.project, action='inspect')
        selected = use_guide(project=self.project, action='select', select=1, guide_id=saved['guide_id'])
        self.assertEqual(selected['selected_opportunity'], 'opportunity-2')

    def test_completed_opportunity_points_to_method_instead_of_duplicate_build_pitch(self):
        helper = test_capability_maps.CapabilityMapTests()
        helper.project = self.project
        helper.cases = ec.read(ec.ROOT / 'fixtures/opportunities/cases.json')
        helper.test_select_flows_to_complete_build_without_asset_type_or_application_input()
        view = library_view(self.project)
        op = next(o for o in view['collections'][0]['opportunities'] if o['opportunity_id'] == 'opportunity-2')
        self.assertEqual(op['status'], 'already_built')
        self.assertEqual(view['references'][op['method_reference']]['status'], 'ready')

    def test_guide_cannot_claim_unavailable_host_memory_as_automatic_input(self):
        self.build()
        draft = self.draft()
        self.assertEqual(draft['context'], [])
        bad = copy.deepcopy(draft)
        bad['context'] = [{'context_id':'unknown','text':'Assumed occupation','origin':'inferred_from_sources',
            'source':'Saved corpus topics','status':'provided'}]
        with self.assertRaises(ec.Invalid): self.save(bad)

    def test_guide_tampering_detected(self):
        self.build(); saved = self.save(self.draft())
        path = self.project / '.expertise-compiler/use-guides' / (saved['guide_id'] + '.json')
        record = ec.read(path); record['draft']['cards'][0]['output'] = 'Changed output'
        ec.write(path, record)
        with self.assertRaisesRegex(ec.Invalid, 'hash'):
            use_guide(project=self.project, action='show')

    def test_new_installed_cli_contains_library_and_guide(self):
        from install_skill import install
        self.build(); self.save(self.draft())
        installed = install(self.base / 'Skills/expertise-compiler')
        result = subprocess.run([sys.executable, '-B', str(installed / 'scripts/ec.py'), 'library',
            '--project', str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['references'])

    def test_legacy_package_visible_without_migration(self):
        done = self.build()
        package = Path(done['method']).parent
        destination = self.project / '.expertise-compiler/capabilities/earlier' / package.name
        shutil.copytree(package, destination)
        before = self.hashes()
        view = library_view(self.project)
        self.assertEqual(len(view['legacy_methods']), 1)
        self.assertEqual(view['legacy_methods'][0]['method'], str(destination / 'SKILL.md'))
        self.assertEqual(view['legacy_methods'][0]['status'], 'saved_version')
        self.assertEqual(view['issues'], [])
        self.assertEqual(before, self.hashes())

    def test_legacy_saved_transcripts_are_not_reported_as_empty_library(self):
        from workflow import compile_workflow
        first = compile_workflow(str(ec.ROOT / 'fixtures/debugging'), project=self.project)
        self.assertEqual(first['phase'], 'extract')
        before = self.hashes()
        view = library_view(self.project)
        self.assertEqual(len(view['legacy_runs']), 1)
        self.assertEqual(view['legacy_runs'][0]['status'], 'sources_saved')
        self.assertNotIn('No saved collections', view['markdown'])
        self.assertEqual(before, self.hashes())


if __name__ == '__main__': unittest.main()
