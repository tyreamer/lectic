"""Acceptance coverage for automatic knowledge relationships and composition."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
from collection_store import Library
from demo import build
from intelligence import assess_import, compose_context, explain_collection, knowledge_graph
from lectic_mcp import Server


class IntelligentKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve(); isolate_home(self, self.base)
        self.project = self.base / 'project'; self.project.mkdir()
        run = build(self.base / 'evidence')
        library = Library(self.project)
        for name in ('Travel', 'My Travel Preferences', 'Europe Travel', 'Photography', 'React'):
            library.archive(adopt=run, name=name)

    def test_travel_context_combines_only_relevant_knowledge(self):
        result = compose_context(self.project, 'Help me plan a European vacation',
                                 '10 days in Italy with an $8,000 budget')
        names = [x['name'] for x in result['using']]
        self.assertIn('Travel', names)
        self.assertIn('Europe Travel', names)
        self.assertIn('My Travel Preferences', names)
        self.assertNotIn('React', names)
        self.assertNotIn('Photography', names)
        self.assertFalse(result['task_context']['persistent'])
        self.assertTrue(result['portable_context'].startswith(('# WayKit context', '# Lectic context')))

    def test_personal_knowledge_and_specialization_are_inferred(self):
        graph = knowledge_graph(self.project)
        layers = {x['name']:x['layer'] for x in graph['collections']}
        self.assertEqual(layers['My Travel Preferences'], 'personal')
        names = {x['collection_id']:x['name'] for x in graph['collections']}
        rels = {(names[r['from']], names[r['to']], r['kind']) for r in graph['relationships']}
        self.assertIn(('Europe Travel', 'Travel', 'specializes'), rels)
        self.assertIn(('My Travel Preferences', 'Travel', 'personal_preference_relevant_to'), rels)
        self.assertTrue(all(r['evidence'] for r in graph['relationships']))

    def test_gap_is_helpful_and_does_not_block_available_context(self):
        result = compose_context(self.project, 'Plan me seven days in Japan')
        self.assertTrue(result['knowledge'])
        self.assertEqual(result['gaps'][0]['topic'], 'Japan')
        self.assertIn("can use", result['gaps'][0]['message'])

    def test_explain_and_mcp_surface_plain_data(self):
        explanation = explain_collection(self.project, 'Europe Travel')
        self.assertEqual(explanation['layer'], 'domain')
        self.assertTrue(explanation['sources'])
        server = Server(self.project)
        response = server.call('lectic_context', {'intent':'plan a trip to Italy'})
        payload = json.loads(response['content'][0]['text'])
        self.assertIn('Europe Travel', [x['name'] for x in payload['using']])

    def test_import_plan_prefers_enrichment_for_small_overlap(self):
        decision = assess_import(self.project, title='Three Europe travel train tips')
        self.assertEqual(decision['decision'], 'enrich_existing')
        self.assertNotIn('ontology', decision['message'].lower())


if __name__ == '__main__': unittest.main()
