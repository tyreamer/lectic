"""Acceptance and unit tests for CloudLibrary.

Verifies:
1. Multi-tenant isolation between separate accounts (Alice and Bob).
2. Save -> Learn -> Organize -> Retrieval -> Application lifecycle.
3. Preservation of evidence and distinction between observed statements and interpretations.
4. Export and local restore round trip.
5. Saving alone never extracts or triggers compilation.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from account_service import AccountStore, AuthorizationError
from cloud_library import CloudLibrary
from collection_store import Library
from home_archive import merge_archive


class CloudLibraryTests(unittest.TestCase):
    def test_account_operations_do_not_use_or_mutate_the_local_home(self):
        from home import storage_root
        local = self.root / 'local'
        Library(local, home=local).archive(name='Local Only')
        with patch.dict(os.environ, {'WAYKIT_HOME': str(local)}):
            saved = self.lib_alice.save_knowledge(text='Keep account notes private.', collections=['Alice Notes'])
            self.assertEqual(saved['collections'], ['Alice Notes'])
            self.lib_alice.learn_from_source(text='Ask about recent examples before proposing a solution.', collection='Alice Methods')
            using = self.lib_alice.get_relevant_context('proposing a solution')['using']
            self.assertIn('Alice Methods', [c['name'] for c in using])
            self.assertFalse(self.lib_bob.get_relevant_context('proposing a solution')['knowledge'])
            self.assertEqual(storage_root(self.root), local.resolve())
        self.assertEqual([c['name'] for c in Library(local, home=local).index['collections']], ['Local Only'])

    def test_explicit_relationship_retrieval_and_private_export(self):
        from organization import organize
        from intelligence import knowledge_graph
        from support import at_home
        self.lib_alice.learn_from_source(text='Check the total number of cards before committing.', collection='SBC Methods')
        self.lib_alice.learn_from_source(text='Compare team alternatives.', collection='Ultimate Team')
        self.lib_alice.organize_knowledge(action='link', source_collection='SBC Methods',
            target_collection='Ultimate Team', relationship='part_of', reason='SBC decisions are part of team strategy')
        fresh = CloudLibrary(self.alice['account_id'], self.root)
        self.assertIn('SBC Methods', [p['name'] for p in fresh.get_relevant_context('Ultimate Team')['using']])
        with self.assertRaises(AuthorizationError):
            self.lib_bob.organize_knowledge(action='link', source_collection='SBC Methods',
                target_collection='Ultimate Team', relationship='part_of', reason='Not my data')
        destination = self.root / 'restored'
        with at_home(destination):
            report = merge_archive(destination, fresh.export_library())
            self.assertFalse(report['issues'])
            graph = knowledge_graph(destination)
            self.assertTrue(any(r['kind'] == 'part_of' for r in graph['relationships']))
            organize(destination, action='unlink', source_collection='SBC Methods',
                     target_collection='Ultimate Team', relationship='part_of')
            merge_archive(destination, fresh.export_library())
            self.assertFalse(any(r['kind'] == 'part_of' for r in knowledge_graph(destination)['relationships']))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.accounts = AccountStore(self.root)

        # Create two accounts
        self.alice = self.accounts.create_account('alice@example.com', 'password123', 'Alice')
        self.bob = self.accounts.create_account('bob@example.com', 'password123', 'Bob')

        self.lib_alice = CloudLibrary(self.alice['account_id'], self.root, self.accounts)
        self.lib_bob = CloudLibrary(self.bob['account_id'], self.root, self.accounts)

    def test_save_knowledge_does_not_extract_or_compile(self):
        result = self.lib_alice.save_knowledge(
            text="High hydration sourdough (75%+) requires coil folds every 30 minutes during bulk fermentation.",
            title="Sourdough Fermentation Notes",
            note="Saved for next weekend bake"
        )
        self.assertTrue(result['saved'])
        self.assertIn('capture_id', result)
        self.assertTrue(result['collections'])
        self.assertIn('Saved only', result['note'])

        # Verify nothing was compiled or converted to IR yet
        home_alice = self.accounts.get_account_home(self.alice['account_id'])
        self.assertFalse(list(home_alice.rglob('ir.json')))

    def test_learn_from_source_preserves_evidence_and_distinguishes_status(self):
        # 1. Save text
        save_res = self.lib_alice.save_knowledge(
            text="Rule 1: Always check proofing temperature. If the kitchen is below 70F, extend bulk fermentation by 2 hours.",
            title="Sourdough Temperature Guide",
            collections=('Sourdough',)
        )

        # 2. Learn from it
        learn_res = self.lib_alice.learn_from_source(
            capture_id=save_res['capture_id'],
            collection='Sourdough Baking'
        )
        self.assertEqual(learn_res['phase'], 'learned')
        self.assertGreater(learn_res['units_learned'], 0)
        self.assertTrue(all(u['evidence_count'] > 0 for u in learn_res['units']))
        self.assertTrue(all(u['status'] in {'observed', 'inferred', 'synthesized'} for u in learn_res['units']))

        # Verify IR exists now
        home_alice = self.accounts.get_account_home(self.alice['account_id'])
        self.assertTrue(list(home_alice.rglob('ir.json')))

    def test_organize_and_relate_knowledge(self):
        # Create general pack
        self.lib_alice.learn_from_source(
            text="Travel rules: Check passport validity at least six months before departure to prevent airline boarding denials.",
            title="General Travel",
            collection="Travel"
        )
        # Create specialized pack
        self.lib_alice.learn_from_source(
            text="European rail travel: Book high speed trains between European capitals at least 30 days early for best rates.",
            title="Europe Rail Tips",
            collection="Europe Travel"
        )
        # Create personal preference pack
        self.lib_alice.learn_from_source(
            text="My preference: I always prefer morning flights and window seats for transatlantic trips.",
            title="Flight Preferences",
            collection="My Travel Preferences"
        )

        # Organize knowledge
        org = self.lib_alice.organize_knowledge(action='infer')
        self.assertEqual(org['phase'], 'organized')
        rels = org['relationships']
        col_names = {c['collection_id']: c['name'] for c in org['collections']}
        rel_tuples = {(col_names[r['from']], col_names[r['to']], r['kind']) for r in rels}

        self.assertIn(('Europe Travel', 'Travel', 'specializes'), rel_tuples)
        self.assertIn(('My Travel Preferences', 'Travel', 'personal_preference_relevant_to'), rel_tuples)

    def test_fresh_session_retrieval_and_application(self):
        # Setup knowledge in Alice's library
        self.lib_alice.learn_from_source(
            text="Debugging rule: Always reproduce the bug with a minimal test before attempting any code fix.",
            title="Debugging Method",
            collection="Software Engineering"
        )

        # In a "fresh session", simulate query to apply knowledge
        context = self.lib_alice.get_relevant_context(
            intent="Review my plan to fix a bug in the payment gateway",
            task_context="A user reported timeout on checkout."
        )
        self.assertTrue(any(u['collection'] == 'Software Engineering' for u in context['knowledge']))
        self.assertFalse(context['task_context']['persistent'])

        # Apply knowledge
        applied = self.lib_alice.apply_knowledge(
            intent="Review my plan to fix a bug in the payment gateway",
            task_context="A user reported timeout on checkout."
        )
        self.assertEqual(applied['phase'], 'applied')
        self.assertTrue(len(applied['checklist']) > 0)
        self.assertIn("minimal test", applied['applied_result'])

    def test_multi_user_isolation(self):
        # Alice saves private secret
        self.lib_alice.learn_from_source(
            text="Alice's confidential project strategy: Focus entirely on enterprise B2B sales in Q4.",
            title="Strategy",
            collection="Alice Private Secrets"
        )

        # Bob saves public baking
        self.lib_bob.learn_from_source(
            text="Baking: Flour, water, salt, yeast.",
            title="Bread 101",
            collection="Baking"
        )

        # Bob searches for Alice's secrets
        bob_search = self.lib_bob.search_knowledge("enterprise B2B sales")
        self.assertEqual(bob_search['total_matches'], 0)
        self.assertEqual(len(bob_search['results']), 0)

        # Bob attempts to get context for Alice's secrets
        bob_context = self.lib_bob.get_relevant_context("enterprise B2B sales")
        self.assertNotIn("Alice Private Secrets", [c['name'] for c in bob_context['using']])
        self.assertEqual(len(bob_context['knowledge']), 0)

        # Bob attempts to access Alice's collection by name or guessed ID
        alice_col_id = self.lib_alice.library.index['collections'][0]['collection_id']
        with self.assertRaises(AuthorizationError):
            self.lib_bob.organize_knowledge(action='explain', source_collection=alice_col_id)

        with self.assertRaises(AuthorizationError):
            self.lib_bob.organize_knowledge(action='explain', source_collection="Alice Private Secrets")

    def test_export_library_and_restore_locally(self):
        # Alice creates knowledge
        self.lib_alice.learn_from_source(
            text="Machine learning tip: Always split training, validation, and test sets before any feature engineering.",
            title="ML Standards",
            collection="Machine Learning"
        )

        # Alice exports library
        export_bytes = self.lib_alice.export_library()
        self.assertIsInstance(export_bytes, bytes)
        self.assertGreater(len(export_bytes), 100)

        # Restore into a separate local Lectic home
        local_home = self.root / 'local_user_home'
        local_home.mkdir()
        merge_report = merge_archive(local_home, export_bytes, home=local_home)

        self.assertEqual(merge_report['phase'], 'home_merged')
        self.assertIn('Machine Learning', merge_report['collections_added'])

        # Verify local Lectic Library sees the restored collection and IR
        local_lib = Library(local_home, home=local_home)
        self.assertEqual(len(local_lib.index['collections']), 1)
        col_entry = local_lib.index['collections'][0]
        self.assertEqual(col_entry['name'], 'Machine Learning')
        folder, data = local_lib.resolve(col_entry['collection_id'])
        run = local_lib.run(folder, data)
        self.assertTrue((run / 'ir.json').is_file())


if __name__ == '__main__':
    unittest.main()
