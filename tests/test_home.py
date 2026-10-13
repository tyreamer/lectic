"""One Lectic home per user: knowledge saved from one project is visible from every other."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from home import DEFAULT_DIRNAME, LEGACY_DIRNAME, home_scope, relative_run, resolve_run, session_path, storage_mode, storage_root
from home_migration import centralize
from goal_workflow import work
from workflow import compile_workflow
import test_workflow


class HomeResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'Project'; self.project.mkdir()
        environment = patch.dict(os.environ, {}, clear=False)
        environment.start(); self.addCleanup(environment.stop)
        os.environ.pop('WAYKIT_HOME', None); os.environ.pop('LECTIC_HOME', None)

    def test_environment_variable_wins(self):
        home = isolate_home(self, self.base)
        self.assertEqual(storage_root(self.project), home.resolve())
        self.assertEqual(storage_mode(storage_root(self.project), self.project), 'explicit')

    def test_existing_project_local_storage_cannot_shadow_the_shared_home(self):
        os.environ.pop('LECTIC_HOME', None)
        legacy = self.project / LEGACY_DIRNAME; (legacy / 'collections').mkdir(parents=True)
        with patch('home.Path.home', return_value=self.base / 'fake-user'):
            root = storage_root(self.project)
            self.assertEqual(root, (self.base / 'fake-user' / DEFAULT_DIRNAME).resolve())
            self.assertEqual(storage_mode(root, self.project), 'user')

    def test_scratch_folder_with_legacy_name_does_not_capture_the_home(self):
        os.environ.pop('LECTIC_HOME', None)
        (self.project / LEGACY_DIRNAME / 'inbox').mkdir(parents=True)
        with patch('home.Path.home', return_value=self.base / 'fake-user'):
            self.assertEqual(storage_root(self.project), (self.base / 'fake-user' / DEFAULT_DIRNAME).resolve())
        ec.write(self.project / LEGACY_DIRNAME / 'library.json', {})
        with patch('home.Path.home', return_value=self.base / 'fake-user'):
            self.assertEqual(storage_root(self.project), (self.base / 'fake-user' / DEFAULT_DIRNAME).resolve())

    def test_project_directories_named_runs_or_collections_are_not_libraries(self):
        (self.project / 'runs').mkdir(); (self.project / 'collections').mkdir()
        with patch('home.Path.home', return_value=self.base / 'fake-user'):
            self.assertEqual(storage_root(self.project), (self.base / 'fake-user' / DEFAULT_DIRNAME).resolve())

    def test_a_library_index_in_a_project_cannot_redirect_the_shared_home(self):
        ec.write(self.project / 'library.json', {'schema_version': '1.0', 'collections': [], 'active_collection': None})
        with patch('home.Path.home', return_value=self.base / 'fake-user'):
            self.assertEqual(storage_root(self.project), (self.base / 'fake-user' / DEFAULT_DIRNAME).resolve())

    def test_account_scope_overrides_local_environment_then_restores_it(self):
        local = isolate_home(self, self.base)
        account = self.base / 'account-home'
        with home_scope(account):
            self.assertEqual(storage_root(self.project), account.resolve())
        self.assertEqual(storage_root(self.project), local.resolve())

    def test_default_is_user_home_not_project(self):
        os.environ.pop('LECTIC_HOME', None)
        with patch('home.Path.home', return_value=self.base / 'fake-user'):
            root = storage_root(self.project)
        self.assertEqual(root, (self.base / 'fake-user' / DEFAULT_DIRNAME).resolve())
        self.assertEqual(storage_mode(root, self.project), 'user')
        self.assertTrue(session_path(root, self.project).is_relative_to(root / 'sessions'))
        self.assertNotEqual(session_path(root, self.project), session_path(root, self.base / 'Other'))

    def test_run_paths_prefer_home_and_accept_legacy_session_values(self):
        home = isolate_home(self, self.base)
        run = home / 'runs' / 'demo'; run.mkdir(parents=True); ec.write(run / 'corpus.json', {})
        self.assertEqual(relative_run(home, self.project, run), 'runs/demo')
        self.assertEqual(resolve_run(home, self.project, 'runs/demo'), run.resolve())
        # A session written by a project-local install recorded the same run under its old prefix.
        self.assertEqual(resolve_run(home, self.project, LEGACY_DIRNAME + '/runs/demo'), run.resolve())
        explicit = self.project / 'legacy-out'; explicit.mkdir(); ec.write(explicit / 'corpus.json', {})
        self.assertEqual(relative_run(home, self.project, explicit), 'legacy-out')
        self.assertEqual(resolve_run(home, self.project, 'legacy-out'), explicit.resolve())
        with self.assertRaises(ec.Invalid): relative_run(home, self.project, self.base / 'elsewhere')
        with self.assertRaises(ec.Invalid): resolve_run(home, self.project, 'runs/missing')


class SharedHomeTests(unittest.TestCase):
    seed = test_workflow.WorkflowTests.seed

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = isolate_home(self, self.base)
        self.oracle = None

    def test_collections_saved_in_one_project_are_visible_from_another(self):
        first = self.base / 'Client Work'; first.mkdir()
        second = self.base / 'Personal Notes'; second.mkdir()
        saved = work(project=first, input=str(ec.ROOT / 'fixtures/debugging'), name='Debugging Methods', action='save')
        self.assertEqual(saved['phase'], 'archived')
        listing = work(project=second, action='list')
        self.assertEqual([c['name'] for c in listing['collections']], ['Debugging Methods'])
        self.assertEqual(listing['home'], str(self.home.resolve()))
        self.assertEqual(listing['storage_mode'], 'explicit')
        self.assertFalse((first / LEGACY_DIRNAME).exists()); self.assertFalse((second / LEGACY_DIRNAME).exists())
        # Reuse from the second project resolves the collection by name without re-upload.
        self.assertEqual(work(project=second, collection='Debugging Methods', action='inspect')['summary']['source_count'], 1)

    def test_legacy_session_resumes_after_switching_to_a_shared_home(self):
        project = self.base / 'Old Project'; project.mkdir()
        legacy = project / LEGACY_DIRNAME; (legacy / 'runs').mkdir(parents=True)
        with patch.dict(os.environ, {'LECTIC_HOME': str(legacy)}):
            run = Path(compile_workflow(str(ec.ROOT / 'fixtures/photography'), project=project)['run'])
        self.assertTrue(run.is_relative_to(legacy))
        session = ec.read(session_path(legacy, project)); session['active_run'] = LEGACY_DIRNAME + '/runs/' + run.name
        ec.write(legacy / 'session.json', session)
        self.seed(run)
        imported = centralize(project)
        self.assertTrue(imported['session_imported'])
        self.assertTrue(Path(imported['backup']).is_file())
        self.assertTrue(run.is_dir())
        self.assertEqual(compile_workflow(project=project)['phase'], 'reconcile')
        self.assertTrue(Path(compile_workflow(project=project)['run']).is_relative_to(self.home))

    def test_centralize_merges_collections_without_overwrite_and_can_repeat(self):
        project = self.base / 'Old Project'; project.mkdir()
        legacy = project / LEGACY_DIRNAME
        with patch.dict(os.environ, {'LECTIC_HOME': str(legacy)}):
            work(project=project, input=str(ec.ROOT / 'fixtures/debugging'), name='Old Knowledge', action='save')
        work(project=project, input=str(ec.ROOT / 'fixtures/photography'), name='Central Knowledge', action='save')
        report = centralize(project)
        self.assertEqual(report['collections_added'], ['Old Knowledge'])
        self.assertEqual(report['issues'], [])
        self.assertTrue(report['original_preserved'])
        self.assertTrue(Path(report['backup']).is_file())
        repeated = centralize(project)
        self.assertEqual(repeated['collections_added'], [])
        self.assertEqual(repeated['collections_present'], ['Old Knowledge'])
        other = self.base / 'Other Project'; other.mkdir()
        self.assertEqual({c['name'] for c in work(project=other, action='list')['collections']},
                         {'Old Knowledge', 'Central Knowledge'})


if __name__ == '__main__':
    unittest.main()
