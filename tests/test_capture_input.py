"""Minimal producer contract and real importer/processing integration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ec
from capture_store import CaptureStore


class CaptureInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.inbox = self.base / 'Inbox'
        self.inbox.mkdir()
        self.project = self.base / 'Project'
        self.store = CaptureStore(self.project)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, text, name='item.capture.json', **extra):
        value = {'captured_at': '2026-09-15T12:00:00-04:00', 'original_value': text, **extra}
        path = self.inbox / name
        ec.write(path, value)
        return path

    def test_url_minimum_becomes_canonical_capture_without_processing(self):
        self.put('https://example.com/talk')
        result = self.store.import_folder(self.inbox)
        self.assertFalse(result['needs_attention'])
        self.assertFalse(result['items'][0]['processing_performed'])
        event, state = self.store.all()[0]
        ec.validate_schema(event, 'capture')
        self.assertEqual(event['captured_at'], '2026-09-15T12:00:00-04:00')
        self.assertEqual(state['processing_status'], 'awaiting_retrieval')
        self.assertEqual(state['source_ids'], [])
        self.assertEqual(self.store.listing()['items'][0]['collections'], ['Inbox'])
        self.assertFalse(list(self.project.rglob('ir.json')))

    def test_exact_shared_text_preserved_and_notes_are_separate(self):
        text = '  "Check" permissions.\nKeep \\ paths, café and 🍝.\n'
        self.put(text, user_note='Not policy.', requested_collections=['Architecture', 'Security'])
        self.store.import_folder(self.inbox)
        event, _ = self.store.all()[0]
        self.assertEqual(event['original_value'], text)
        self.assertEqual(event['shared_text'], text)
        self.assertEqual(event['source_type'], 'text')
        self.store.process('Architecture')
        sources = list((self.store.root / 'sources').iterdir())
        self.assertEqual(len(sources), 1)
        _, docs, _ = ec.validate_sources(sources[0])
        self.assertNotIn('Not policy.', json.dumps(docs))
        self.assertEqual(self.store.listing()['items'][0]['user_context'][0]['note'], 'Not policy.')

    def test_fresh_session_reimport_after_rename_and_mtime_change(self):
        path = self.put('Keep original material.')
        self.store.import_folder(self.inbox)
        original = self.store.all()[0][0]
        path.rename(self.inbox / 'renamed.capture.json')
        folder = self.base / 'Different sync location'
        shutil.copytree(self.inbox, folder)
        os.utime(folder / 'renamed.capture.json', (1700000000, 1700000000))
        fresh = CaptureStore(self.project)
        self.assertFalse(fresh.import_folder(folder)['items'][0]['new'])
        self.assertEqual(fresh.all()[0][0], original)
        self.assertEqual(len(fresh.all()), 1)

    def test_later_save_has_new_capture_but_reuses_source(self):
        self.put('Same supplied procedure.', 'first.capture.json')
        self.put('Same supplied procedure.', 'second.capture.json', captured_at='2026-09-16T12:00:00-04:00')
        self.store.import_folder(self.inbox)
        self.store.process('Inbox')
        rows = self.store.all()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0][0]['capture_id'], rows[1][0]['capture_id'])
        self.assertEqual(rows[0][1]['source_ids'], rows[1][1]['source_ids'])

    def test_shared_excerpt_and_multiple_urls_keep_all_text(self):
        text = 'Inspect permissions (https://example.com/talk). Also https://example.org/other'
        self.put(text)
        self.store.import_folder(self.inbox)
        event, _ = self.store.all()[0]
        self.assertEqual(event['url'], 'https://example.com/talk')
        self.assertEqual(event['original_value'], text)
        self.assertEqual(event['source_type'], 'text')
        self.store.process('Inbox')
        self.assertEqual(self.store.listing()['items'][0]['processing_status'], 'partially_processed')

    def test_url_only_never_normalizes_into_transcript(self):
        self.put('  https://example.com/talk?x=1&y=two#part  \n')
        self.store.import_folder(self.inbox)
        event, state = self.store.all()[0]
        self.store.normalize_item(event, state)
        self.assertEqual(state['source_ids'], [])
        self.assertEqual(event['url'], 'https://example.com/talk?x=1&y=two#part')

    def test_uppercase_url_scheme_is_still_a_link(self):
        self.put('HTTPS://example.com/talk')
        self.store.import_folder(self.inbox)
        event, state = self.store.all()[0]
        self.assertEqual(event['source_type'], 'url')
        self.assertEqual(event['url'], 'HTTPS://example.com/talk')
        self.assertEqual(state['processing_status'], 'awaiting_retrieval')

    def test_bad_inputs_isolated_and_retry_after_sync(self):
        self.put('Valid item.')
        bad = self.inbox / 'arriving.capture.json'
        bad.write_text('{"captured_at":', encoding='utf-8')
        self.assertEqual(len(self.store.import_folder(self.inbox)['needs_attention']), 1)
        self.put('Arrived later.', bad.name)
        self.assertFalse(self.store.import_folder(self.inbox)['needs_attention'])
        self.assertEqual(len(self.store.all()), 2)

    def test_invalid_metadata_rejected_without_records(self):
        cases = [None, [], 'text', {},
            {'captured_at': '2026-09-15', 'original_value': 'No timezone.'},
            {'captured_at': 'not a time', 'original_value': 'Bad date.'},
            {'captured_at': '2026-09-15T12:00:00Z', 'original_value': '   '},
            {'captured_at': '2026-09-15T12:00:00Z', 'original_value': 'Valid', 'title': 'Invented'},
            {'captured_at': '2026-09-15T12:00:00Z', 'original_value': 123}]
        for value in cases:
            with self.subTest(value=value):
                ec.write(self.inbox / 'bad.capture.json', value)
                self.assertEqual(len(self.store.import_folder(self.inbox)['needs_attention']), 1)
                self.assertEqual(self.store.all(), [])

    def test_existing_canonical_and_annotation_format_still_works(self):
        self.put('Minimal input.')
        for name in ['shortcut-url.json', 'shortcut-annotation.note.json']:
            shutil.copyfile(ec.ROOT / 'fixtures/capture' / name, self.inbox / name)
        report = self.store.import_folder(self.inbox)
        self.assertFalse(report['needs_attention'])
        self.assertEqual(len(report['items']), 2)
        self.assertEqual(len(report['annotations']), 1)

    def test_optional_context_cannot_rewrite_existing_capture(self):
        self.put('Original content.', user_note='First note.')
        self.store.import_folder(self.inbox)
        self.put('Original content.', user_note='Changed note.')
        self.assertEqual(len(self.store.import_folder(self.inbox)['needs_attention']), 1)
        self.assertEqual(self.store.all()[0][0]['user_note'], 'First note.')

    def test_no_accidental_import_of_arbitrary_json_or_text_files(self):
        self.put('Unmarked input.', name='arbitrary.json')
        (self.inbox / 'notes.txt').write_text('Not a capture.', encoding='utf-8')
        report = self.store.import_folder(self.inbox)
        self.assertEqual(len(report['needs_attention']), 1)
        self.assertEqual(report['items'], [])

    def test_sample_and_installed_cli_use_same_adapter(self):
        from install_skill import install
        shutil.copyfile(ec.ROOT / 'fixtures/capture/simple-url.capture.json', self.inbox / 'sample.capture.json')
        installed = install(self.base / 'Skills/expertise-compiler')
        result = subprocess.run([sys.executable, '-B', str(installed / 'scripts/ec.py'),
            'capture', '--project', str(self.project), '--action', 'import', '--inbox', str(self.inbox)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['needs_attention'])
        self.assertEqual(len(self.store.all()), 1)


if __name__ == '__main__':
    unittest.main()
