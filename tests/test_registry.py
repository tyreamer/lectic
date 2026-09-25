from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import isolate_home
import ec
from demo import build
from goal_workflow import work
from packs import build_pack
from identity import save_identity
from registry import (
    fetch_registry, search_registry, resolve_registry_pack,
    inspect_registry_pack, format_search_results, format_inspect_report,
    prepare_registry_entry
)
import cli
from lectic_mcp import Server


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.oracle = build(self.base / 'oracle')
        self.author = self.base / 'author'
        self.author.mkdir()
        self.home = isolate_home(self, self.base, 'author-home')

    def seed(self, run):
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def prepared_collection(self, name, inputs):
        folder = self.author / ('input-' + ec.digest(name.encode())[:6])
        folder.mkdir()
        for filename, source in inputs.items():
            shutil.copy(source, folder / filename)
        result = work(project=self.author, input=str(folder), name=name, action='save')
        self.seed(result['run'])
        result = work(project=self.author, collection=name, action='prepare', reconciled=True)
        self.assertEqual(result['phase'], 'knowledge_saved')
        return result

    def test_bundled_registry_validates_schema(self):
        root = Path(__file__).resolve().parents[1]
        schema = ec.read(root / 'schemas' / 'registry.schema.json')
        index = ec.read(root / 'registry' / 'index.json')
        ec.validate_schema(index, 'registry')
        self.assertGreaterEqual(len(index['packs']), 4)
        for pack in index['packs']:
            self.assertIn('name', pack)
            self.assertIn('title', pack)
            self.assertIn('publisher', pack)
            self.assertIn('url', pack)
            self.assertIn('version', pack)
            self.assertIn('tags', pack)

    def test_search_registry_queries_and_tags(self):
        # All packs
        all_packs = search_registry(project=self.author)
        self.assertGreaterEqual(len(all_packs), 4)

        # Query filter
        eng_packs = search_registry(query='distributed', project=self.author)
        self.assertEqual(len(eng_packs), 1)
        self.assertEqual(eng_packs[0]['name'], 'distributed-systems-adr')

        # Tag filter
        testing_packs = search_registry(tag='testing', project=self.author)
        self.assertEqual(len(testing_packs), 1)
        self.assertEqual(testing_packs[0]['name'], 'engineering-standards')

        # No matches
        empty = search_registry(query='nonexistent_pack_xyz', project=self.author)
        self.assertEqual(len(empty), 0)

    def test_format_search_results(self):
        packs = search_registry(query='growth', project=self.author)
        formatted = format_search_results(packs, query='growth')
        self.assertIn('growth-frameworks', formatted)
        self.assertIn('TR', formatted)
        self.assertIn('lectic install registry:growth-frameworks', formatted)

        # Empty formatting
        empty_formatted = format_search_results([], query='xyz')
        self.assertIn("No packs found matching 'xyz'", empty_formatted)

    def test_resolve_registry_pack(self):
        # By slug
        entry = resolve_registry_pack('engineering-standards', project=self.author)
        self.assertEqual(entry['name'], 'engineering-standards')
        self.assertEqual(entry['publisher'], 'Lectic Core Team')

        # With registry: prefix
        entry2 = resolve_registry_pack('registry:engineering-standards', project=self.author)
        self.assertEqual(entry2['name'], 'engineering-standards')

        # Case-insensitive
        entry3 = resolve_registry_pack('registry:ENGINEERING-STANDARDS', project=self.author)
        self.assertEqual(entry3['name'], 'engineering-standards')

        # Invalid pack name raises Invalid
        with self.assertRaises(ec.Invalid):
            resolve_registry_pack('registry:unknown-pack-404', project=self.author)

    def test_inspect_registry_pack_and_formatting(self):
        info = inspect_registry_pack('registry:fifa-market-tactics', project=self.author)
        self.assertEqual(info['registry_entry']['name'], 'fifa-market-tactics')
        self.assertIn('Market Dip Opportunity Scanner', info['methods'])
        self.assertIn('lectic install registry:fifa-market-tactics', info['install_command'])

        formatted = format_inspect_report(info)
        self.assertIn('FUT Accountant', formatted)
        self.assertIn('Install:     lectic install registry:fifa-market-tactics', formatted)
        self.assertIn('Market Dip Opportunity Scanner', formatted)

    def test_prepare_registry_entry_for_signed_pack(self):
        inputs = {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'}
        self.prepared_collection('Camera Tactics', inputs)

        # Unsigned fails
        pack_res = build_pack(self.author, 'Camera Tactics', team=True, version='2026-09-25')
        pack_file = pack_res['pack']
        with self.assertRaises(ec.Invalid) as ctx:
            prepare_registry_entry(self.author, pack_file, 'https://example.com/camera.lectic')
        self.assertIn('Registry submission requires a signed pack', str(ctx.exception))

        # Set identity and re-pack
        save_identity(str(self.author), 'Alice Photographer', 'alice@photo.org')
        pack_res2 = build_pack(self.author, 'Camera Tactics', team=True, version='2026-09-25')
        entry = prepare_registry_entry(self.author, pack_res2['pack'], 'https://example.com/camera.lectic', tags=['camera', 'media'])

        self.assertEqual(entry['name'], 'camera-tactics')
        self.assertEqual(entry['publisher'], 'Alice Photographer')
        self.assertEqual(entry['url'], 'https://example.com/camera.lectic')
        self.assertEqual(entry['version'], '2026-09-25')
        self.assertEqual(entry['tags'], ['camera', 'media'])
        self.assertGreater(entry['units'], 0)

        # Validate generated entry against schema
        temp_registry = {
            'schema_version': '1.0',
            'updated_at': '2026-09-25T15:00:00Z',
            'packs': [entry]
        }
        ec.validate_schema(temp_registry, 'registry')

    def test_cli_search_and_inspect(self):
        # CLI search
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['search', 'systems'])
        self.assertEqual(code, 0)
        self.assertIn('distributed-systems-adr', buf.getvalue())

        # CLI search --json
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['search', 'systems', '--json'])
        self.assertEqual(code, 0)
        parsed = json.loads(buf.getvalue())
        self.assertIsInstance(parsed, list)
        self.assertEqual(parsed[0]['name'], 'distributed-systems-adr')

        # CLI inspect registry:NAME
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['inspect', 'registry:growth-frameworks'])
        self.assertEqual(code, 0)
        self.assertIn('growth-frameworks', buf.getvalue())
        self.assertIn('Pricing Leverage Evaluator', buf.getvalue())

    def test_mcp_search_and_inspect_tools(self):
        server = Server(project=str(self.author))

        # Test lectic_search tool
        res = server.call('lectic_search', {'query': 'distributed'})
        self.assertFalse(res['isError'])
        content = json.loads(res['content'][0]['text'])
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]['name'], 'distributed-systems-adr')

        # Test lectic_inspect tool
        res_inspect = server.call('lectic_inspect', {'target': 'registry:engineering-standards'})
        self.assertFalse(res_inspect['isError'])
        inspect_data = json.loads(res_inspect['content'][0]['text'])
        self.assertIn('Deterministic Test Verifier', inspect_data['methods'])
        self.assertEqual(inspect_data['registry_entry']['name'], 'engineering-standards')

    def test_install_registry_pack_resolves_and_installs(self):
        inputs = {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'}
        self.prepared_collection('Architecture Notes', inputs)
        save_identity(str(self.author), 'Alice Architect', 'alice@arch.org')
        pack_res = build_pack(self.author, 'Architecture Notes', team=True, version='1.0.0')

        mock_entry = {
            'name': 'arch-notes',
            'title': 'Architecture Notes',
            'publisher': 'Alice Architect',
            'url': pack_res['pack'],
            'install_name': 'architecture',
            'version': '1.0.0',
            'tags': ['architecture']
        }

        with patch('registry.resolve_registry_pack', return_value=mock_entry):
            # Test CLI install registry:arch-notes --pin
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(['install', 'registry:arch-notes', '--pin'])
            self.assertEqual(code, 0)
            self.assertIn('Installed architecture [pinned: v1.0.0]', buf.getvalue())

            # Test MCP tool_install with registry: prefix
            server = Server(project=str(self.author))
            res = server.call('lectic_install', {'location': 'registry:arch-notes', 'as_name': 'mcp-arch', 'pin': True})
            self.assertFalse(res['isError'])
            data = json.loads(res['content'][0]['text'])
            self.assertEqual(data['collection'], 'mcp-arch')
            self.assertTrue(data['pinned'])


if __name__ == '__main__':
    unittest.main()
