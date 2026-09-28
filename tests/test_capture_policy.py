"""The save decision itself: where an item lands, and what Lectic admits it can read.

Covers the four placement paths, the source-type honesty matrix, local-vs-hosted
reach, and one hosted assistant driving the whole loop over real HTTP.
"""
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from capture_policy import describe_source
from demo import build
from goal_workflow import work
from lectic_mcp import Server, connect_url, serve_http

DEBUG_SRT = ec.ROOT / 'fixtures/debugging/debugging.srt'


class PlacementBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.oracle = None
        self.project = self.base / 'project'
        self.project.mkdir()
        self.home = isolate_home(self, self.base)

    def _seed(self, run):
        if self.oracle is None:
            self.oracle = build(self.base / 'oracle')
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def add_collection(self, name):
        folder = self.project / ('input-' + ec.digest(name.encode())[:6])
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEBUG_SRT, folder / DEBUG_SRT.name)
        result = work(project=self.project, input=str(folder), name=name, action='save')
        self._seed(result['run'])
        work(project=self.project, collection=name, action='prepare', reconciled=True)

    def save(self, **kwargs):
        return Server(self.project).tool_capture_save(**kwargs)


class PlacementDecisionTests(PlacementBase):
    def test_named_collection_is_honored_without_a_question(self):
        result = self.save(url='https://example.com/anything', collections=['Dinner Ideas'])
        self.assertEqual(result['decision'], 'explicit')
        self.assertEqual(result['collections'], ['Dinner Ideas'])
        self.assertEqual(result['question'], '')
        self.assertIn('Dinner Ideas', result['confirmation'])

    def test_one_strong_match_files_itself_and_says_where(self):
        self.add_collection('Database Indexing')
        result = self.save(url='https://example.com/postgres', title='PostgreSQL Database Indexing Optimization')
        self.assertEqual(result['decision'], 'auto_filed')
        self.assertEqual(result['collections'], ['Database Indexing'])
        self.assertEqual(result['question'], '')
        self.assertIn('Database Indexing', result['confirmation'])

    def test_several_plausible_matches_ask_exactly_one_question(self):
        self.add_collection('Python Performance Optimization')
        self.add_collection('Python Debugging Tools')
        result = self.save(url='https://example.com/py', title='Python profiling and debugging performance')
        self.assertEqual(result['decision'], 'needs_clarification')
        self.assertEqual(result['collections'], ['Inbox'])
        self.assertGreaterEqual(len(result['candidate_collections']), 2)
        for candidate in result['candidate_collections']:
            self.assertIn(candidate['name'], result['question'])
        self.assertIn('somewhere new', result['question'])
        self.assertEqual(result['question'].count('?'), 1)
        self.assertIn(result['question'], result['confirmation'])

    def test_no_plausible_match_goes_to_inbox_and_says_so(self):
        self.add_collection('Machine Learning Systems')
        result = self.save(url='https://example.com/pastry', title='Gourmet French Pastry and Croissant Baking')
        self.assertEqual(result['decision'], 'inbox_fallback')
        self.assertEqual(result['collections'], ['Inbox'])
        self.assertEqual(result['candidate_collections'], [])
        self.assertEqual(result['question'], '')
        self.assertIn('Inbox', result['confirmation'])
        self.assertIn('close fit', result['confirmation'])

    def test_empty_library_falls_back_to_inbox(self):
        result = self.save(text='a thought with nowhere to go yet')
        self.assertEqual(result['decision'], 'inbox_fallback')
        self.assertEqual(result['collections'], ['Inbox'])

    def test_auto_filed_item_is_actually_a_member_of_that_collection(self):
        self.add_collection('Database Indexing')
        result = self.save(url='https://example.com/postgres', title='PostgreSQL Database Indexing Optimization')
        listing = Server(self.project).tool_capture(action='list', collection='Database Indexing')
        self.assertIn(result['capture_id'], [i['capture_id'] for i in listing['items']])


class SourceTypeHonestyTests(PlacementBase):
    def test_youtube_link_promises_captions(self):
        source = describe_source(url='https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.assertEqual(source['source_type'], 'youtube')
        self.assertEqual(source['retrieval'], 'captions')
        self.assertTrue(source['content_available'])
        self.assertIn('captions', source['what_lectic_gets'])

    def test_instagram_link_is_reference_only(self):
        result = self.save(url='https://www.instagram.com/p/ABC123/', note='great framing')
        self.assertEqual(result['source']['source_type'], 'web')
        self.assertEqual(result['source']['platform'], 'Instagram')
        self.assertEqual(result['source']['retrieval'], 'reference_only')
        self.assertFalse(result['source']['content_available'])
        self.assertIn('Instagram links are saved as a reference only', result['confirmation'])

    def test_tiktok_and_plain_web_links_are_reference_only(self):
        for url, platform in (('https://www.tiktok.com/@a/video/1', 'TikTok'), ('https://blog.example.com/post', 'blog.example.com')):
            source = describe_source(url=url)
            self.assertEqual(source['retrieval'], 'reference_only')
            self.assertFalse(source['content_available'])
            self.assertEqual(source['platform'], platform)

    def test_pasted_text_is_quotable(self):
        source = describe_source(text='the exact words')
        self.assertEqual(source['retrieval'], 'supplied_text')
        self.assertTrue(source['content_available'])


class ReachTests(PlacementBase):
    def test_stdio_server_warns_that_hosted_chats_cannot_reach_it(self):
        info = Server(self.project).tool_home()
        self.assertEqual(info['transport'], 'stdio')
        self.assertIn('ChatGPT', info['reach'])
        self.assertIn('lectic share', info['reach'])

    def test_http_server_reports_itself_as_reachable_over_a_link(self):
        httpd = serve_http(self.project, port=0, announce=None)
        self.addCleanup(httpd.server_close)
        info = httpd.mcp.tool_home()
        self.assertEqual(info['transport'], 'http')
        self.assertIn('shared HTTP link', info['reach'])


class HostedAssistantLoopTests(PlacementBase):
    """A hosted assistant only ever sees tools/call over HTTP. Drive the whole loop that way."""

    def setUp(self):
        super().setUp()
        self.httpd = serve_http(self.project, port=0, announce=None)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.endpoint = connect_url(f'http://127.0.0.1:{self.httpd.server_address[1]}', self.httpd.token)
        self.counter = 0
        self.rpc('initialize', protocolVersion='2025-06-18', capabilities={}, clientInfo={'name': 'hosted', 'version': '0'})

    def rpc(self, method, **params):
        self.counter += 1
        body = json.dumps({'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params}).encode('utf-8')
        request = urllib.request.Request(self.endpoint, data=body, method='POST',
                                         headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        self.assertNotIn('error', payload)
        return payload['result']

    def call(self, name, **arguments):
        result = self.rpc('tools/call', name=name, arguments=arguments)
        self.assertFalse(result['isError'], result['content'][0]['text'])
        return json.loads(result['content'][0]['text'])

    def test_ambiguous_save_asks_once_then_lands_where_the_user_said(self):
        self.add_collection('Python Performance Optimization')
        self.add_collection('Python Debugging Tools')

        saved = self.call('lectic_capture_save', url='https://example.com/py', title='Python profiling and debugging performance')
        self.assertEqual(saved['decision'], 'needs_clarification')
        self.assertEqual(saved['collections'], ['Inbox'])
        self.assertIn('somewhere new', saved['question'])
        self.assertIn('Python Debugging Tools', saved['question'])

        self.call('lectic_capture', action='move', items=[saved['capture_id']], to=['Python Debugging Tools'])

        chosen = self.call('lectic_capture', action='list', collection='Python Debugging Tools')
        self.assertIn(saved['capture_id'], [i['capture_id'] for i in chosen['items']])
        inbox = self.call('lectic_capture', action='list', collection='Inbox')
        self.assertNotIn(saved['capture_id'], [i['capture_id'] for i in inbox['items']])

    def test_unmatched_save_lands_in_inbox_and_admits_it(self):
        self.add_collection('Machine Learning Systems')
        saved = self.call('lectic_capture_save', url='https://www.instagram.com/p/XYZ/', title='Sourdough starter tips')
        self.assertEqual(saved['decision'], 'inbox_fallback')
        self.assertEqual(saved['collections'], ['Inbox'])
        self.assertIn('reference only', saved['confirmation'])
        inbox = self.call('lectic_capture', action='list', collection='Inbox')
        self.assertIn(saved['capture_id'], [i['capture_id'] for i in inbox['items']])


if __name__ == '__main__':
    unittest.main()
