"""Tests for candidate collection matching and collection selection enforcement."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from demo import build
from goal_workflow import work
from candidate_collections import find_candidate_collections
from lectic_mcp import Server


class CandidateCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.oracle = build(self.base / 'oracle')
        self.project = self.base / 'project'
        self.project.mkdir()
        self.home = isolate_home(self, self.base)

    def _seed(self, run):
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def _add_collection(self, name, fixture_file, metadata=None):
        folder = self.project / ('input-' + ec.digest(name.encode())[:6])
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy(fixture_file, folder / fixture_file.name)
        meta = None
        if metadata:
            meta = folder.parent / (folder.name + '.json')
            ec.write(meta, metadata)
        result = work(project=self.project, input=str(folder), metadata=str(meta) if meta else None, name=name, action='save')
        self._seed(result['run'])
        work(project=self.project, collection=name, action='prepare', reconciled=True)

    def test_no_collections_returns_no_collections_action(self):
        result = find_candidate_collections(self.project, url='https://youtube.com/watch?v=123', title='Some video')
        self.assertFalse(result['has_collections'])
        self.assertEqual(result['total_collections'], 0)
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['all_collections'], [])
        self.assertEqual(result['suggested_action'], 'no_collections')
        self.assertIn('first collection', result['prompt_guidance'])

    def test_creator_match_returns_candidate_with_reason(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        metadata = {
            'debugging.srt': {
                'url': 'https://www.youtube.com/watch?v=debug123',
                'title': 'Systematic Debugging Workshop',
                'creator': 'Dr. Software Engineering'
            }
        }
        self._add_collection('Software Debugging', debug_srt, metadata)

        # Incoming content matches creator
        res = find_candidate_collections(self.project, text='Dr. Software Engineering explains break points in python')
        self.assertTrue(res['has_collections'])
        self.assertEqual(len(res['candidates']), 1)
        top = res['candidates'][0]
        self.assertEqual(top['name'], 'Software Debugging')
        self.assertGreaterEqual(top['score'], 0.4)
        self.assertTrue(any('creator' in r.lower() for r in top['reasons']))
        self.assertEqual(res['suggested_action'], 'ask_with_candidates')

    def test_topic_keyword_match_on_collection_name(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._add_collection('Python Performance Optimization', debug_srt)

        res = find_candidate_collections(self.project, title='Tips for Python Optimization and Memory Profiling')
        self.assertEqual(len(res['candidates']), 1)
        top = res['candidates'][0]
        self.assertEqual(top['name'], 'Python Performance Optimization')
        self.assertTrue(any('keyword' in r.lower() or 'collection name' in r.lower() for r in top['reasons']))

    def test_unrelated_content_returns_no_candidates_and_lists_all(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._add_collection('Machine Learning Systems', debug_srt)

        res = find_candidate_collections(self.project, title='Gourmet French Pastry and Croissant Baking')
        self.assertEqual(len(res['candidates']), 0)
        self.assertEqual(res['total_collections'], 1)
        self.assertEqual(len(res['all_collections']), 1)
        self.assertEqual(res['all_collections'][0]['name'], 'Machine Learning Systems')
        self.assertEqual(res['suggested_action'], 'ask_all_collections')

    def test_multi_collection_ranks_best_match_first(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._add_collection('Early-Cycle Market Trading', debug_srt, {
            'debugging.srt': {'url': 'https://example.com/1', 'title': 'Market Opening Strategies', 'creator': 'MarketTrader'}
        })
        self._add_collection('Standup Comedy Writing', debug_srt, {
            'debugging.srt': {'url': 'https://example.com/2', 'title': 'Punchline Timing', 'creator': 'ComedyWriter'}
        })

        res = find_candidate_collections(self.project, title='MarketTrader on Overnight Trading Setups')
        self.assertGreaterEqual(len(res['candidates']), 1)
        self.assertEqual(res['candidates'][0]['name'], 'Early-Cycle Market Trading')
        self.assertEqual(len(res['all_collections']), 2)

    def test_mcp_tool_collection_candidates(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._add_collection('Web Security Auditing', debug_srt)

        server = Server(self.project)
        call_res = server.call('lectic_collection_candidates', {'url': 'https://example.com/vuln', 'title': 'Web Security Exploit Analysis'})
        self.assertFalse(call_res['isError'])
        data = json.loads(call_res['content'][0]['text'])
        self.assertTrue(data['has_collections'])
        self.assertEqual(len(data['candidates']), 1)
        self.assertEqual(data['candidates'][0]['name'], 'Web Security Auditing')

    def test_mcp_tool_library_with_matching_parameters(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._add_collection('Cloud Architecture', debug_srt)

        server = Server(self.project)
        call_res = server.call('lectic_library', {'title': 'Cloud Architecture Best Practices'})
        self.assertFalse(call_res['isError'])
        data = json.loads(call_res['content'][0]['text'])
        self.assertIn('candidate_collections', data)
        self.assertEqual(len(data['candidate_collections']), 1)
        self.assertEqual(data['candidate_collections'][0]['name'], 'Cloud Architecture')

    def test_mcp_tool_capture_save_without_collections_surfaces_candidates(self):
        debug_srt = ec.ROOT / 'fixtures/debugging/debugging.srt'
        self._add_collection('Database Indexing', debug_srt)

        server = Server(self.project)
        call_res = server.call('lectic_capture_save', {'url': 'https://example.com/postgres', 'title': 'PostgreSQL Database Indexing Optimization'})
        self.assertFalse(call_res['isError'])
        data = json.loads(call_res['content'][0]['text'])
        self.assertEqual(data['phase'], 'captured')
        self.assertIn('candidate_collections', data)
        self.assertEqual(len(data['candidate_collections']), 1)
        self.assertEqual(data['candidate_collections'][0]['name'], 'Database Indexing')
        self.assertIn('warning', data)


if __name__ == '__main__':
    unittest.main()
