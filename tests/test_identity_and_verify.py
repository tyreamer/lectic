"""Tests for lectic identity (pack signing) and verify (evidence linkage) features."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home, at_home
import ec
from demo import build
from goal_workflow import work
from identity import (
    load_identity, save_identity, show_identity,
    sign_manifest, verify_manifest, check_manifest_signature,
    identity_path, _key_id, _sign, _verify,
)
from packs import build_pack, inspect_pack, open_pack
from verify import verify_collection, format_report


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'project'
        self.project.mkdir()
        self.home = isolate_home(self, self.base)

    def test_no_identity_returns_none(self):
        self.assertIsNone(load_identity(self.project))

    def test_show_identity_prompts_when_none_set(self):
        msg = show_identity(self.project)
        self.assertIn('No identity', msg)
        self.assertIn('lectic identity set', msg)

    def test_save_and_load_identity(self):
        record = save_identity(str(self.project), 'Alice Example', 'alice@example.com')
        self.assertEqual(record['name'], 'Alice Example')
        self.assertEqual(record['contact'], 'alice@example.com')
        self.assertIsInstance(record['key_id'], str)
        self.assertEqual(len(record['key_id']), 64)
        self.assertIsInstance(record['key_hex'], str)
        self.assertEqual(len(record['key_hex']), 64)  # 32 bytes = 64 hex chars

        loaded = load_identity(self.project)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['name'], 'Alice Example')
        self.assertEqual(loaded['contact'], 'alice@example.com')
        self.assertEqual(loaded['key_id'], record['key_id'])
        self.assertEqual(loaded['key_hex'], record['key_hex'])

    def test_save_identity_replaces_existing(self):
        save_identity(str(self.project), 'Old Name', 'old@example.com')
        save_identity(str(self.project), 'New Name', 'new@example.com')
        loaded = load_identity(self.project)
        self.assertEqual(loaded['name'], 'New Name')
        self.assertEqual(loaded['contact'], 'new@example.com')

    def test_show_identity_displays_when_set(self):
        save_identity(str(self.project), 'Bob', 'bob@example.com')
        msg = show_identity(self.project)
        self.assertIn('Bob', msg)
        self.assertIn('bob@example.com', msg)
        self.assertIn('Key ID', msg)

    def test_key_id_is_stable(self):
        """Same key always produces the same key_id."""
        key_hex = 'a' * 64
        id1 = _key_id(key_hex)
        id2 = _key_id(key_hex)
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 16)

    def test_sign_and_verify_round_trip(self):
        key_hex = 'b' * 64
        data = b'hello world manifest bytes'
        sig = _sign(data, key_hex)
        self.assertTrue(_verify(data, sig, key_hex))

    def test_verify_rejects_altered_data(self):
        key_hex = 'c' * 64
        data = b'original bytes'
        sig = _sign(data, key_hex)
        self.assertFalse(_verify(b'tampered bytes', sig, key_hex))

    def test_verify_rejects_bad_signature(self):
        key_hex = 'd' * 64
        data = b'some manifest'
        self.assertFalse(_verify(data, 'deadbeef' * 8, key_hex))

    def test_verify_rejects_wrong_key(self):
        key_hex_a = 'e' * 64
        key_hex_b = 'f' * 64
        data = b'some manifest'
        sig = _sign(data, key_hex_a)
        self.assertFalse(_verify(data, sig, key_hex_b))

    def test_sign_manifest_produces_publisher_block(self):
        identity = save_identity(str(self.project), 'Charlie', 'charlie@example.com')
        manifest = {'name': 'Test Pack', 'pack_id': 'pack-abc', 'files': {}, 'ir_hash': 'xyz'}
        publisher = sign_manifest(manifest, identity)
        self.assertEqual(publisher['name'], 'Charlie')
        self.assertEqual(publisher['contact'], 'charlie@example.com')
        self.assertEqual(publisher['key_id'], identity['key_id'])
        self.assertIsInstance(publisher['signature'], str)
        self.assertEqual(len(publisher['signature']), 128)  # Ed25519: 64 bytes

    def test_verify_manifest_passes_for_own_pack(self):
        identity = save_identity(str(self.project), 'Diana', 'diana@example.com')
        manifest = {'name': 'Test Pack', 'pack_id': 'pack-abc', 'files': {}, 'ir_hash': 'xyz'}
        publisher = sign_manifest(manifest, identity)
        manifest['publisher'] = publisher
        ok, msg = verify_manifest(manifest, identity)
        self.assertTrue(ok)
        self.assertIn('Valid Ed25519', msg)

    def test_verify_manifest_fails_for_tampered_manifest(self):
        identity = save_identity(str(self.project), 'Eve', 'eve@example.com')
        manifest = {'name': 'Test Pack', 'pack_id': 'pack-abc', 'files': {}, 'ir_hash': 'xyz'}
        publisher = sign_manifest(manifest, identity)
        manifest['publisher'] = publisher
        manifest['name'] = 'Tampered Pack Name'  # alter a signed field
        ok, msg = verify_manifest(manifest, identity)
        self.assertFalse(ok)
        self.assertIn('invalid', msg)

    def test_check_manifest_signature_unsigned(self):
        manifest = {'name': 'Test', 'pack_id': 'pack-abc'}
        status, msg = check_manifest_signature(manifest)
        self.assertEqual(status, 'unsigned')
        self.assertIn('No publisher', msg)
        self.assertIn('lectic identity', msg)

    def test_check_manifest_signature_signed(self):
        identity = save_identity(str(self.project), 'Frank', 'frank@example.com')
        manifest = {'name': 'Test Pack', 'pack_id': 'pack-abc', 'files': {}, 'ir_hash': 'xyz'}
        manifest['publisher'] = sign_manifest(manifest, identity)
        status, msg = check_manifest_signature(manifest)
        self.assertEqual(status, 'signed')
        self.assertIn('Frank', msg)
        self.assertIn('frank@example.com', msg)
        self.assertIn(identity['key_id'], msg)


class PackSigningTests(unittest.TestCase):
    """Test that build_pack signs when identity exists, and that open_pack still validates."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.oracle = build(self.base / 'oracle')
        self.author = self.base / 'author'
        self.author.mkdir()
        self.home = isolate_home(self, self.base, 'author-home')

    def _seed(self, run):
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def _prepared_collection(self, name):
        import shutil
        folder = self.author / ('input-' + ec.digest(name.encode())[:6])
        folder.mkdir()
        shutil.copy(ec.ROOT / 'fixtures/debugging/debugging.srt', folder / 'debugging.srt')
        result = work(project=self.author, input=str(folder), name=name, action='save')
        self._seed(result['run'])
        result = work(project=self.author, collection=name, action='prepare', reconciled=True)
        self.assertEqual(result['phase'], 'knowledge_saved')
        return result

    def test_pack_is_unsigned_when_no_identity(self):
        self._prepared_collection('Test Knowledge')
        packed = build_pack(self.author, 'Test Knowledge', self.base / 'out.lectic', include_sources=True)
        self.assertEqual(packed.get('publisher'), '')
        manifest, _ = open_pack(Path(packed['pack']).read_bytes())
        self.assertNotIn('publisher', manifest)
        status, _ = check_manifest_signature(manifest)
        self.assertEqual(status, 'unsigned')

    def test_pack_is_signed_when_identity_exists(self):
        save_identity(str(self.author), 'Test Signer', 'signer@example.com')
        self._prepared_collection('Signed Knowledge')
        packed = build_pack(self.author, 'Signed Knowledge', self.base / 'out.lectic', include_sources=True)
        self.assertIn('Test Signer', packed.get('publisher', ''))
        manifest, _ = open_pack(Path(packed['pack']).read_bytes())
        self.assertIn('publisher', manifest)
        pub = manifest['publisher']
        self.assertEqual(pub['name'], 'Test Signer')
        self.assertEqual(pub['contact'], 'signer@example.com')
        status, msg = check_manifest_signature(manifest)
        self.assertEqual(status, 'signed')
        self.assertIn('Test Signer', msg)

    def test_signed_pack_still_passes_open_pack_integrity_check(self):
        """pack_id verification must account for publisher being added after pack_id is derived."""
        save_identity(str(self.author), 'Integrity Tester', 'integrity@example.com')
        self._prepared_collection('Integrity Check')
        packed = build_pack(self.author, 'Integrity Check', self.base / 'integrity.lectic', include_sources=True)
        # open_pack raises Invalid if the pack_id doesn't match — no exception = pass
        manifest, members = open_pack(Path(packed['pack']).read_bytes())
        self.assertEqual(manifest['publisher']['name'], 'Integrity Tester')

    def test_inspect_pack_shows_publisher_status(self):
        save_identity(str(self.author), 'Inspector Tester', 'inspect@example.com')
        self._prepared_collection('Inspector Knowledge')
        packed = build_pack(self.author, 'Inspector Knowledge', self.base / 'inspect.lectic', include_sources=True)
        info = inspect_pack(packed['pack'])
        self.assertEqual(info['publisher_status'], 'signed')
        self.assertIn('Inspector Tester', info['publisher_info'])

    def test_inspect_unsigned_pack_shows_unsigned_status(self):
        self._prepared_collection('Unsigned Knowledge')
        packed = build_pack(self.author, 'Unsigned Knowledge', self.base / 'unsigned.lectic', include_sources=True)
        info = inspect_pack(packed['pack'])
        self.assertEqual(info['publisher_status'], 'unsigned')


class VerifyTests(unittest.TestCase):
    """Test lectic verify against compiled collections."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.oracle = build(self.base / 'oracle')
        self.project = self.base / 'project'
        self.project.mkdir()
        self.home = isolate_home(self, self.base)

    def _seed(self, run):
        import shutil
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def _prepared_collection(self, name, srt_path):
        import shutil
        folder = self.project / ('input-' + ec.digest(name.encode())[:6])
        folder.mkdir()
        shutil.copy(srt_path, folder / srt_path.name)
        result = work(project=self.project, input=str(folder), name=name, action='save')
        self._seed(result['run'])
        result = work(project=self.project, collection=name, action='prepare', reconciled=True)
        self.assertEqual(result['phase'], 'knowledge_saved')

    def test_verify_compiled_collection_passes(self):
        srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._prepared_collection('Debug Knowledge', srt)
        report = verify_collection(self.project, 'Debug Knowledge')
        self.assertEqual(report['collection'], 'Debug Knowledge')
        self.assertIn(report['overall'], ('verified', 'partial'))  # may be partial without blob store
        self.assertGreater(report['units']['total'], 0)
        self.assertEqual(report['units']['broken'], 0)  # broken evidence linkage must be 0
        self.assertIn('unit_results', report)

    def test_verify_report_format_is_ascii_safe(self):
        srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._prepared_collection('Format Check', srt)
        report = verify_collection(self.project, 'Format Check')
        text = format_report(report)
        # All characters must be encodable in ASCII-safe manner (no Unicode symbols)
        text.encode('ascii')  # raises UnicodeEncodeError if not

    def test_verify_returns_structured_report(self):
        srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._prepared_collection('Structure Check', srt)
        report = verify_collection(self.project, 'Structure Check')
        required_keys = {'collection', 'collection_id', 'overall', 'units', 'sources', 'unit_results', 'source_issues'}
        self.assertTrue(required_keys.issubset(report.keys()))
        unit_keys = {'total', 'verified', 'partial', 'broken', 'no_evidence'}
        self.assertTrue(unit_keys.issubset(report['units'].keys()))

    def test_verify_unit_result_structure(self):
        srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._prepared_collection('Unit Result Check', srt)
        report = verify_collection(self.project, 'Unit Result Check')
        for result in report['unit_results']:
            self.assertIn('unit_id', result)
            self.assertIn('status', result)
            self.assertIn(result['status'], ('verified', 'partial', 'broken', 'no_evidence'))
            self.assertIn('evidence_ok', result)
            self.assertIn('evidence_total', result)
            self.assertIn('failures', result)


if __name__ == '__main__':
    unittest.main()
