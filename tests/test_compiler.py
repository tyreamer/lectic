import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from demo import build
from evaluate import prepare, score


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.home = isolate_home(self, self.base)
        self.run = build(self.base / 'demo')

    def tearDown(self):
        self.temp.cleanup()

    def test_end_to_end_three_domains_and_portable_validation(self):
        ir = ec.validate_ir(self.run)
        self.assertEqual(len(ir['units']), 12)
        self.assertEqual(len(ir['coverage']), 4)
        self.assertIn('synthesized', {u['status'] for u in ir['units']})
        for folder in (self.base / 'demo' / 'packages').iterdir():
            result = subprocess.run([sys.executable, str(folder / 'checks' / 'validate.py')], cwd=self.base,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            ec.validate_package(folder)

    def test_ingest_resumes_identical_snapshot(self):
        before = (self.run / 'corpus.json').read_bytes()
        ec.ingest(ec.ROOT / 'fixtures/transcripts', self.run, ec.ROOT / 'fixtures/metadata.json')
        self.assertEqual(before, (self.run / 'corpus.json').read_bytes())

    def test_changed_inputs_need_new_run(self):
        inputs = self.base / 'input'; inputs.mkdir()
        (inputs / 'one.txt').write_text('First source.', encoding='utf-8')
        ec.ingest(inputs, self.base / 'other')
        (inputs / 'one.txt').write_text('Changed source.', encoding='utf-8')
        with self.assertRaisesRegex(ec.Invalid, 'changed'): ec.ingest(inputs, self.base / 'other')

    def test_caption_and_plain_speaker_timing(self):
        vtt = b'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Alice>Hello &amp; hi</v>\n'
        s = ec.normalize(vtt, '.vtt')[0]
        self.assertEqual((s['speaker'], s['start'], s['end'], s['text']), ('Alice', 1.0, 2.0, 'Hello & hi'))
        plain = ec.normalize(b'[00:05] Ada: First\nBob: Second', '.txt')
        self.assertEqual(len(plain), 2)
        self.assertEqual((plain[0]['start'], plain[0]['speaker'], plain[0]['raw_text']), (5.0, 'Ada', '[00:05] Ada: First'))
        self.assertEqual(plain[1]['speaker'], 'Bob')

    def test_malformed_and_empty_captions_fail(self):
        for content in [b'WEBVTT\n\nbad caption', b'WEBVTT', b'00:00:60.000 --> 00:00:61.000\nx', b'00:00:04.000 --> 00:00:02.000\nx']:
            with self.subTest(content=content), self.assertRaises(ec.Invalid): ec.normalize(content, '.vtt')

    def test_duplicate_contents_keep_distinct_sources(self):
        inputs = self.base / 'input'; inputs.mkdir()
        for name in ['one.txt', 'two.txt']: (inputs / name).write_text('Same content.', encoding='utf-8')
        c = ec.ingest(inputs, self.base / 'duplicates')
        self.assertEqual(len({e['source_id'] for e in c['sources']}), 2)

    def test_invalid_metadata_rejected_before_output(self):
        meta = self.base / 'bad.json'
        for value in [{'unknown.txt': {}}, {'gardening.txt': {'creator': 123}}, {'gardening.txt': {'url': 'javascript:bad'}}, {'gardening.txt': {'extra': 'bad'}}]:
            ec.write(meta, value)
            with self.subTest(value=value), self.assertRaises(ec.Invalid):
                ec.ingest(ec.ROOT / 'fixtures/transcripts', self.base / 'bad-run', meta)
            self.assertFalse((self.base / 'bad-run').exists())

    def test_raw_hash_tampering_detected(self):
        _, docs, _ = ec.validate_sources(self.run)
        raw = self.run / next(iter(docs.values()))['raw_path']
        raw.write_bytes(raw.read_bytes() + b' Changed')
        with self.assertRaisesRegex(ec.Invalid, 'hash'): ec.validate_sources(self.run)

    def test_segment_tamper_detected_even_with_updated_document_hash(self):
        corpus = ec.read(self.run / 'corpus.json')
        entry = corpus['sources'][0]
        doc = ec.read(self.run / entry['path'])
        doc['segments'][0]['text'] = 'Fabricated evidence'
        ec.write(self.run / entry['path'], doc)
        entry['document_hash'] = ec.fingerprint(doc)
        corpus['corpus_id'] = 'corpus-' + ec.fingerprint(corpus['sources'])
        ec.write(self.run / 'corpus.json', corpus)
        with self.assertRaisesRegex(ec.Invalid, 'Segments differ'): ec.validate_sources(self.run)

    def test_ir_mutation_failures(self):
        original = ec.read(self.run / 'ir.json')
        mutations = [
            lambda d: d['units'].append(copy.deepcopy(d['units'][0])),
            lambda d: d['units'][0]['evidence'][0].update(quote='Not present in this source.'),
            lambda d: d['units'][0]['evidence'][0].update(segment_id='seg-999999'),
            lambda d: d['units'][0].update(status='inferred', derivation=''),
            lambda d: d['units'][0].update(confidence=0.99),
            lambda d: d['units'][0]['relations'].append({'kind':'requires','target':'absent'}),
            lambda d: d['units'][0]['attribution'][0].update(name='Imaginary person'),
            lambda d: d['coverage'].pop(),
            lambda d: d.update(schema_version='2.0'),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(original); mutation(changed)
            ec.write(self.run / 'ir.json', changed)
            with self.subTest(mutation=mutation), self.assertRaises(ec.Invalid): ec.validate_ir(self.run)

    def test_stale_capabilities_fail(self):
        ir = ec.read(self.run / 'ir.json')
        ir['units'][0]['statement'] += ' Updated.'
        ec.write(self.run / 'ir.json', ir)
        with self.assertRaisesRegex(ec.Invalid, 'stale'): ec.validate_capabilities(self.run)

    def test_conflict_cannot_be_dropped(self):
        caps = ec.read(self.run / 'capabilities.json')
        herb = caps['capabilities'][0]
        herb['conflict_policy'] = ''
        ec.write(self.run / 'capabilities.json', caps)
        with self.assertRaisesRegex(ec.Invalid, 'conflict policy'): ec.validate_capabilities(self.run)

    def test_absent_relation_closure_fails(self):
        caps = ec.read(self.run / 'capabilities.json')
        herb = caps['capabilities'][0]
        herb['unit_ids'].remove('herb-opinion-scope')
        for item in herb['steps'] + herb['examples']:
            item['unit_ids'] = [x for x in item['unit_ids'] if x != 'herb-opinion-scope']
        ec.write(self.run / 'capabilities.json', caps)
        with self.assertRaisesRegex(ec.Invalid, 'related units'): ec.validate_capabilities(self.run)

    def test_interruption_and_reassembly(self):
        part = next((self.run / 'units').glob('*.json'))
        saved = part.read_bytes(); part.unlink()
        self.assertEqual(ec.status(self.run)['next'], 'extract')
        with self.assertRaisesRegex(ec.Invalid, 'incomplete'): ec.assemble(self.run)
        part.write_bytes(saved)
        data = ec.read(part); data['units'][0]['statement'] += ' Rephrased.'; ec.write(part, data)
        self.assertEqual(ec.status(self.run)['next'], 'assemble')
        ec.assemble(self.run)
        self.assertEqual(len(list((self.run / 'history').glob('*.json'))), 2)

    def test_package_inventory_detects_changes_and_additions(self):
        folder = self.base / 'demo/packages/container-herb-reviewer'
        path = folder / 'SKILL.md'; before = path.read_bytes()
        path.write_bytes(before + b'Extra directive')
        with self.assertRaisesRegex(ec.Invalid, 'inventory'): ec.validate_package(folder)
        path.write_bytes(before)
        (folder / 'extra.txt').write_text('surprise', encoding='utf-8')
        with self.assertRaisesRegex(ec.Invalid, 'inventory'): ec.validate_package(folder)

    def test_duplicate_json_keys_and_traversal_rejected(self):
        path = self.base / 'duplicate.json'; path.write_text('{"x":1,"x":2}', encoding='utf-8')
        with self.assertRaisesRegex(ec.Invalid, 'duplicate JSON'): ec.read(path)
        for rel in ['../outside', 'C:/outside', '/absolute', '..\\outside']:
            with self.subTest(rel=rel), self.assertRaises(ec.Invalid): ec.safe_child(self.run, rel)

    def test_no_heldout_leak_in_packages(self):
        tasks = ec.read(ec.ROOT / 'fixtures/held-out/tasks.json')
        for path in (self.base / 'demo/packages').rglob('*'):
            if path.is_file():
                content = path.read_text(encoding='utf-8')
                for task in tasks: self.assertNotIn(task['task'], content)

    def test_evaluation_checks_decisions_and_fabricated_quotes(self):
        prepare(self.base / 'demo')
        tasks = ec.read(ec.ROOT / 'fixtures/held-out/tasks.json')
        expected = ec.read(ec.ROOT / 'fixtures/held-out/rubric.json')['expected_decisions']
        responses = [{'case_id': t['case_id'], 'answer': 'Synthetic checker test, not a model evaluation.',
                      'decisions': expected[t['case_id']], 'citations': [{'filename':'gardening.txt', 'quote':'fabricated quotation', 'unit_id':'herb-moisture'}]} for t in tasks]
        path = self.base / 'responses.json'; ec.write(path, responses)
        report = score(self.run, path, 'compiled')
        self.assertEqual(report['decision_matches'], 6)
        self.assertGreater(report['citation_error_count'], 0)
        self.assertFalse(report['quality_win_established'])
        responses[1]['case_id'] = responses[0]['case_id']; ec.write(path, responses)
        with self.assertRaises(ec.Invalid): score(self.run, path, 'compiled')

    def test_cli_nonzero_on_invalid_input(self):
        result = subprocess.run([sys.executable, str(ec.ROOT / 'scripts/ec.py'), 'validate', str(self.base / 'missing')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Error:', result.stderr)


if __name__ == '__main__':
    unittest.main()
