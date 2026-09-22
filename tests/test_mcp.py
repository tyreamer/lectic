"""The MCP server is a complete interface: a client with no file access can run every workflow."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from demo import build
from lectic_mcp import Server, TOOLS


class Client:
    """Drive a Server in-process the way an MCP client would, one JSON-RPC message at a time."""
    def __init__(self, server):
        self.server, self.counter = server, 0

    def request(self, method, **params):
        self.counter += 1
        response = self.server.handle({'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params})
        assert 'error' not in response, response
        return response['result']

    def call(self, tool_name, **arguments):
        result = self.request('tools/call', name=tool_name, arguments=arguments)
        text = result['content'][0]['text']
        if result['isError']: raise ec.Invalid(text)
        try: return json.loads(text)
        except ValueError: return text


class McpWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'Project'; self.project.mkdir()
        self.home = isolate_home(self, self.base)
        self.client = Client(Server(self.project))
        self.client.request('initialize', protocolVersion='2025-06-18', capabilities={}, clientInfo={'name': 'test', 'version': '0'})
        self.server_oracle = None

    def oracle_checkpoints(self, run):
        """Authored fixture checkpoints stand in for the client's reasoning at the extraction boundary."""
        if self.server_oracle is None: self.server_oracle = build(self.base / 'oracle')
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.server_oracle)
        by_name = {d['filename']: d for d in originals.values()}
        for sid, doc in docs.items():
            part = ec.read(self.server_oracle / f"units/{by_name[doc['filename']]['source_id']}.json")
            yield sid, {**part, 'corpus_id': corpus['corpus_id']}

    def test_handshake_lists_tools_and_serves_prompts_as_resources(self):
        init = self.client.server.handle({'jsonrpc': '2.0', 'id': 99, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})['result']
        self.assertEqual(init['protocolVersion'], '2025-06-18')
        self.assertIn('lectic_write_json', init['instructions'])
        self.assertIsNone(self.client.server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
        names = {t['name'] for t in self.client.request('tools/list')['tools']}
        self.assertEqual(names, {t['name'] for t in TOOLS})
        for t in TOOLS: self.assertEqual(t['inputSchema']['additionalProperties'], False)
        uris = {r['uri'] for r in self.client.request('resources/list')['resources']}
        self.assertIn('lectic://prompts/extract.md', uris); self.assertIn('lectic://schemas/brief.schema.json', uris)
        text = self.client.request('resources/read', uri='lectic://prompts/goal-work.md')['contents'][0]['text']
        self.assertEqual(text, (ec.ROOT / 'prompts/goal-work.md').read_text(encoding='utf-8'))
        self.assertEqual(self.client.request('ping'), {})
        unknown = self.client.server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'nope'})
        self.assertEqual(unknown['error']['code'], -32601)

    def test_goal_workflow_completes_through_tools_alone(self):
        c = self.client
        self.assertEqual(c.call('lectic_home')['home'], str(self.home.resolve()))
        brief = {'schema_version': '1.0', 'objective': 'Improve my debugging plan', 'context': 'Small project.',
                 'constraints': ['Use supplied methods.'], 'work': {'label': 'My plan', 'text': 'PRIVATE DRAFT: Change parsing and delimiters together, then ship after one successful file.'},
                 'desired_result': 'A practical improved plan', 'success_criteria': ['Identify unsupported assumptions.']}
        saved = c.call('lectic_write_json', path=str(self.home / 'inbox' / 'brief.json'), value=brief)
        self.assertEqual(saved['kind'], 'brief')
        result = c.call('lectic_work', input=str(ec.ROOT / 'fixtures/debugging'), name='My Methods', brief=saved['saved'])
        self.assertEqual(result['phase'], 'extract')
        task = result['agent_task']
        self.assertIn('Write `RUN/units/SOURCE_ID.json`', c.call('lectic_read', path=task['prompt']))
        run = Path(result['run'])
        # The client reads a source through the tool, then saves its checkpoint where the task said.
        for pending in task['pending_sources']:
            self.assertIn('segments', c.call('lectic_read', path=pending['source']))
        for sid, part in self.oracle_checkpoints(run):
            self.assertEqual(c.call('lectic_write_json', path=str(run / f'units/{sid}.json'), value=part)['kind'], 'extraction checkpoint')
        self.assertEqual(c.call('lectic_work')['phase'], 'reconcile')
        result = c.call('lectic_work', reconciled=True)
        self.assertEqual(result['phase'], 'assess_coverage')
        task = result['agent_task']; draft = task['draft']
        ir = c.call('lectic_read', path=task['ir'])
        ids = {u['unit_id'] for u in ir['units']}
        cap = next(cp for cp in reversed(ec.read(ec.ROOT / 'fixtures/demo_capabilities.json')) if set(cp['unit_ids']) <= ids)
        c.call('lectic_write_json', path=draft + '/coverage.json', value={'schema_version': '1.0', 'brief_id': task['brief_id'], 'ir_hash': task['ir_hash'],
               'decision': 'reuse', 'source_ids': [], 'reason': 'Authored test.', 'unsupported': ['No universal fix.']})
        self.assertEqual(c.call('lectic_work', target='review')['phase'], 'design_method')
        method = {'schema_version': '1.0', 'brief_id': task['brief_id'], 'ir_hash': task['ir_hash'], 'capability': cap}
        c.call('lectic_write_json', path=draft + '/method.json', value=method)
        self.assertEqual(c.call('lectic_work', target='review')['phase'], 'apply_method')
        finding = {'title': 'Isolate the suspected cause', 'priority': 'high', 'assessment': 'Your plan skips a required distinction.',
                   'proposed_change': 'Change one suspected cause at a time.', 'unit_ids': ['debug-isolate']}
        c.call('lectic_write_json', path=draft + '/result.json', value={'schema_version': '1.0', 'brief_id': task['brief_id'], 'ir_hash': task['ir_hash'],
               'method_hash': ec.fingerprint(method), 'target': 'review', 'assessment': 'Revise the plan.', 'findings': [finding],
               'proposed_revision': finding['proposed_change'], 'checklist': [], 'disagreements': [],
               'limitations': ['Synthetic fixture.'], 'unsupported': ['Universal correctness.'], 'additional_general_advice': []})
        self.assertEqual(c.call('lectic_work', target='review')['phase'], 'review_result')
        done = c.call('lectic_work', target='review', reviewed=True)
        self.assertEqual(done['phase'], 'complete')
        self.assertTrue(c.call('lectic_validate_build', folder=done['build'])['valid'])
        self.assertIn('Proposed change', c.call('lectic_read', path=done['result']))
        # The same home answers from another project and through the read-only library view.
        other = self.base / 'Other'; other.mkdir()
        listing = c.call('lectic_work', project=str(other), action='list')
        self.assertEqual([x['name'] for x in listing['collections']], ['My Methods'])
        self.assertEqual(c.call('lectic_library')['collections'][0]['name'], 'My Methods')

    def test_write_policy_admits_only_requested_records_and_validates_them(self):
        c = self.client
        result = c.call('lectic_work', input=str(ec.ROOT / 'fixtures/debugging'), name='Policy', action='save')
        run = Path(result['run'])
        sid = next(iter(ec.validate_sources(run)[1]))
        with self.assertRaisesRegex(ec.Invalid, 'inside the Lectic home'):
            c.call('lectic_write_json', path=str(self.base / 'elsewhere.json'), value={})
        with self.assertRaisesRegex(ec.Invalid, 'immutable'):
            c.call('lectic_write_json', path=str(run.parent.parent / 'builds' / 'build-x' / 'manifest.json'), value={})
        with self.assertRaisesRegex(ec.Invalid, 'Not a record location'):
            c.call('lectic_write_json', path=str(run / 'corpus.json'), value={})
        with self.assertRaisesRegex(ec.Invalid, 'Not a record location'):
            c.call('lectic_write_json', path=str(run / 'ir.json'), value={})
        with self.assertRaisesRegex(ec.Invalid, 'corpus_id'):
            c.call('lectic_write_json', path=str(run / f'units/{sid}.json'), value={'schema_version': '1.0', 'corpus_id': 'corpus-' + '0' * 64, 'source_id': sid, 'note': 'x', 'units': []})
        corpus_id = ec.read(run / 'corpus.json')['corpus_id']
        with self.assertRaisesRegex(ec.Invalid, 'named after a source'):
            c.call('lectic_write_json', path=str(run / 'units/src-000000000000000000000000.json'), value={'schema_version': '1.0', 'corpus_id': corpus_id, 'source_id': sid, 'note': 'x', 'units': []})
        sid, part = next(self.oracle_checkpoints(run))
        part['units'][0]['evidence'][0]['quote'] = 'words that are not in the source'
        with self.assertRaisesRegex(ec.Invalid, 'quote|evidence|segment'):
            c.call('lectic_write_json', path=str(run / f'units/{sid}.json'), value=part)
        self.assertFalse((run / f'units/{sid}.json').exists())
        with self.assertRaisesRegex(ec.Invalid, 'coverage.json, method.json or result.json'):
            c.call('lectic_write_json', path=str(run.parent.parent / 'requests' / 'b' / 'r' / 'review' / 'notes.json'), value={})
        with self.assertRaisesRegex(ec.Invalid, 'Only files inside'):
            c.call('lectic_read', path=str(self.base / 'oracle-secret.txt'))
        # A capture saved through the tool lands in the home's Inbox without any retrieval.
        saved = c.call('lectic_capture_save', url='https://example.com/talk', note='Good framing; not policy', collections=['Ideas'])
        self.assertEqual(saved['phase'], 'captured'); self.assertEqual(saved['import']['items'][0]['saved'], True)
        rows = c.call('lectic_capture', action='list', collection='Ideas')['items']
        self.assertEqual(rows[0]['processing_status'], 'awaiting_retrieval')
        self.assertEqual(rows[0]['user_context'][0]['note'], 'Good framing; not policy')


class McpStdioTests(unittest.TestCase):
    def test_server_speaks_newline_delimited_json_rpc_over_stdio(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); project = base / 'proj'; project.mkdir()
            env = {**os.environ, 'LECTIC_HOME': str(base / 'home'), 'PYTHONIOENCODING': 'utf-8'}
            messages = [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'x', 'version': '0'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'lectic_home', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'lectic_work', 'arguments': {'action': 'list'}}},
            ]
            payload = ''.join(json.dumps(m) + '\n' for m in messages) + 'not json\n'
            process = subprocess.run([sys.executable, '-B', str(ec.ROOT / 'scripts/lectic_mcp.py'), '--project', str(project)],
                                     input=payload, capture_output=True, text=True, encoding='utf-8', env=env)
            self.assertEqual(process.returncode, 0, process.stderr)
            lines = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
            self.assertEqual([m.get('id') for m in lines], [1, 2, 3, None])
            self.assertEqual(lines[0]['result']['protocolVersion'], '2025-03-26')
            home = json.loads(lines[1]['result']['content'][0]['text'])
            self.assertEqual(home['home'], str((base / 'home').resolve())); self.assertEqual(home['mode'], 'explicit')
            self.assertEqual(json.loads(lines[2]['result']['content'][0]['text'])['collections'], [])
            self.assertEqual(lines[3]['error']['code'], -32700)


if __name__ == '__main__':
    unittest.main()
