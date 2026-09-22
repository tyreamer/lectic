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
from home import DEFAULT_DIRNAME, LEGACY_DIRNAME, relative_run, resolve_run, session_path, storage_mode, storage_root
from goal_workflow import work
from workflow import compile_workflow
import test_workflow


class HomeResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'Project'; self.project.mkdir()

    def test_environment_variable_wins(self):
        home = isolate_home(self, self.base)
        self.assertEqual(storage_root(self.project), home.resolve())
        self.assertEqual(storage_mode(storage_root(self.project), self.project), 'explicit')

    def test_existing_project_local_storage_is_detected(self):
        os.environ.pop('LECTIC_HOME', None)
        legacy = self.project / LEGACY_DIRNAME; legacy.mkdir()
        self.assertEqual(storage_root(self.project), legacy.resolve())
        self.assertEqual(storage_mode(legacy, self.project), 'project-local')
        self.assertEqual(session_path(legacy, self.project), legacy / 'session.json')

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
        self.base = Path(self.temp.name)
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
        os.environ.pop('LECTIC_HOME', None)
        legacy = project / LEGACY_DIRNAME; legacy.mkdir()
        run = Path(compile_workflow(str(ec.ROOT / 'fixtures/photography'), project=project)['run'])
        self.assertTrue(run.is_relative_to(legacy))
        self.assertEqual(ec.read(legacy / 'session.json')['active_run'], 'runs/' + run.name)
        # An older install recorded the run relative to the project; that pointer still resolves.
        session = ec.read(legacy / 'session.json'); session['active_run'] = LEGACY_DIRNAME + '/runs/' + run.name
        ec.write(legacy / 'session.json', session)
        self.seed(run)
        self.assertEqual(compile_workflow(project=project)['phase'], 'reconcile')


if __name__ == '__main__':
    unittest.main()
