"""A whole home moves to another machine, an always-on server, or a backup file — by identity, never by overwrite."""
import io
import json
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import at_home, isolate_home
import ec
import home_archive
from demo import build
from goal_workflow import work
from home_archive import archive_home, backup, merge_archive, open_archive, portable, pull, push, restore
from lectic_mcp import connect_url, serve_http


class Machine:
    """A project plus the home that belongs to it. Operations run `with machine:`."""
    def __init__(self, project, home):
        self.project, self.home = project, home

    def __enter__(self):
        self._scope = at_home(self.home); return self._scope.__enter__() and self or self

    def __exit__(self, *exc): return self._scope.__exit__(*exc)

    def collections(self):
        with self: return [c['name'] for c in work(project=self.project, action='list')['collections']]

    def units(self, name):
        with self: return work(project=self.project, collection=name, action='inspect')['summary']['knowledge_units']


class HomeArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        isolate_home(self, self.base, 'unused-home')  # restore the environment after each test
        self.oracle = build(self.base / 'oracle')
        self.laptop = self.machine('laptop')

    def machine(self, name):
        project = self.base / name; project.mkdir()
        return Machine(project, self.base / (name + '-home'))

    def seed(self, run):
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def prepared(self, machine, name, fixture='fixtures/debugging'):
        with machine:
            result = work(project=machine.project, input=str(ec.ROOT / fixture), name=name, action='save')
            self.seed(result['run'])
            self.assertEqual(work(project=machine.project, collection=name, action='prepare', reconciled=True)['phase'], 'knowledge_saved')

    def archive_of(self, machine):
        with machine: return archive_home(machine.home)

    # ---- what travels
    def test_machine_local_identity_never_travels(self):
        self.prepared(self.laptop, 'Debugging Methods')
        for name in ('server.json', 'share-link.json'):
            (self.laptop.home / name).write_text('{"token": "this machine only"}', encoding='utf-8')
        (self.laptop.home / 'sessions').mkdir(exist_ok=True); (self.laptop.home / 'sessions/abc.json').write_text('{}', encoding='utf-8')
        (self.laptop.home / '.locks').mkdir(exist_ok=True); (self.laptop.home / '.locks/capture.lock').write_bytes(b'0')
        manifest, members = open_archive(self.archive_of(self.laptop))
        for unwanted in ('server.json', 'share-link.json'):
            self.assertNotIn(unwanted, members)
        self.assertFalse([p for p in members if p.startswith(('sessions/', '.locks/'))])
        self.assertTrue(any(p.startswith('blobs/') for p in members))
        self.assertIn('library.json', members)
        self.assertEqual([c['name'] for c in manifest['collections']], ['Debugging Methods'])
        self.assertFalse(portable('server.json')); self.assertFalse(portable('sessions/a.json'))
        self.assertTrue(portable('collections/collection-x/collection.json'))

    def test_backup_and_restore_onto_a_bare_machine(self):
        self.prepared(self.laptop, 'Debugging Methods')
        with self.laptop: result = backup(self.laptop.project, self.base / 'archives')
        self.assertTrue(result['file'].endswith('.lectic-home'))
        self.assertEqual(result['collections'], ['Debugging Methods']); self.assertGreater(result['blobs'], 0)

        desktop = self.machine('desktop')
        with desktop: report = restore(desktop.project, result['file'])
        self.assertEqual(report['collections_added'], ['Debugging Methods'])
        self.assertEqual(report['issues'], []); self.assertGreater(report['blobs_added'], 0)
        self.assertEqual(desktop.units('Debugging Methods'), self.laptop.units('Debugging Methods'))
        # Restoring again is a no-op, not a duplicate.
        with desktop: again = restore(desktop.project, result['file'])
        self.assertEqual((again['collections_added'], again['collections_present'], again['blobs_added']), ([], ['Debugging Methods'], 0))
        self.assertEqual(desktop.collections(), ['Debugging Methods'])

    def test_merge_adds_what_is_missing_and_keeps_a_same_named_collection_apart(self):
        self.prepared(self.laptop, 'Debugging Methods')
        archive = self.archive_of(self.laptop)
        desktop = self.machine('desktop')
        self.prepared(desktop, 'Photography', 'fixtures/photography')
        self.prepared(desktop, 'Debugging Methods', 'fixtures/photography')  # same name, different material
        with desktop: report = merge_archive(desktop.project, archive)
        self.assertEqual(report['collections_added'], ['Debugging Methods (2)'])
        self.assertEqual(report['issues'], [])
        self.assertEqual(sorted(desktop.collections()), ['Debugging Methods', 'Debugging Methods (2)', 'Photography'])
        with desktop:
            local = work(project=desktop.project, collection='Debugging Methods', action='inspect')['summary']['sources']
            moved = work(project=desktop.project, collection='Debugging Methods (2)', action='inspect')['summary']['sources']
        self.assertNotEqual(local, moved)  # both survive, neither was overwritten

    def test_identical_collection_on_both_sides_is_recognised_not_duplicated(self):
        self.prepared(self.laptop, 'Debugging Methods')
        archive = self.archive_of(self.laptop)
        desktop = self.machine('desktop')
        with desktop:
            self.assertEqual(merge_archive(desktop.project, archive)['collections_added'], ['Debugging Methods'])
            report = merge_archive(desktop.project, archive)
        self.assertEqual((report['collections_added'], report['collections_present'], report['collections_diverged']),
                         ([], ['Debugging Methods'], []))
        self.assertEqual(desktop.collections(), ['Debugging Methods'])

    def test_a_changed_copy_is_reported_as_diverged_and_nothing_is_overwritten(self):
        self.prepared(self.laptop, 'Debugging Methods')
        archive = self.archive_of(self.laptop)
        desktop = self.machine('desktop')
        with desktop: merge_archive(desktop.project, archive)
        folder = next((desktop.home / 'collections').iterdir())
        record = ec.read(folder / 'collection.json')
        changed = {**record, 'briefs': record['briefs'] + ['brief-' + 'a' * 20]}
        ec.write(folder / 'collection.json', changed)
        with desktop: report = merge_archive(desktop.project, archive)
        self.assertEqual(report['collections_diverged'], ['Debugging Methods'])
        self.assertEqual(report['collections_added'], [])
        self.assertEqual(ec.read(folder / 'collection.json'), changed)  # the local copy is left exactly as it was

    # ---- over the link
    def test_push_moves_a_home_onto_a_running_lectic_and_others_can_pull_it(self):
        self.prepared(self.laptop, 'Debugging Methods')
        server = self.machine('server')
        with server:
            httpd = serve_http(server.project, port=0, announce=None)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)
        link = connect_url(f'http://127.0.0.1:{httpd.server_address[1]}', httpd.token)
        self.assertEqual(server.collections(), [])
        with self.laptop: report = push(self.laptop.project, link)
        self.assertEqual(report['collections_added'], ['Debugging Methods'])
        self.assertGreater(report['sent_bytes'], 0); self.assertEqual(report['issues'], [])
        self.assertEqual(server.collections(), ['Debugging Methods'])

        phone = self.machine('phone')
        with phone: pulled = pull(phone.project, link)
        self.assertEqual(pulled['collections_added'], ['Debugging Methods'])
        self.assertEqual(phone.units('Debugging Methods'), self.laptop.units('Debugging Methods'))
        # The server keeps its own secret: a home carries none.
        self.assertNotIn('server.json', open_archive(self.archive_of(self.laptop))[1])
        with self.laptop, self.assertRaisesRegex(ec.Invalid, 'refused'):
            push(self.laptop.project, connect_url(f'http://127.0.0.1:{httpd.server_address[1]}', 'wrong-secret'))

    def test_link_forms_and_unreachable_servers_are_explained(self):
        self.assertEqual(home_archive.endpoint('https://h/t/s/mcp'), 'https://h/t/s/home')
        self.assertEqual(home_archive.endpoint('https://h/t/s/'), 'https://h/t/s/home')
        self.assertEqual(home_archive.endpoint('https://h/t/s/home'), 'https://h/t/s/home')
        with self.assertRaisesRegex(ec.Invalid, 'Give the link'): home_archive.endpoint('not-a-link')
        self.prepared(self.laptop, 'Debugging Methods')
        with self.laptop, self.assertRaisesRegex(ec.Invalid, 'Could not reach'):
            push(self.laptop.project, 'http://127.0.0.1:9/t/s/mcp')

    # ---- refusals
    def test_unsafe_or_altered_archives_are_refused(self):
        self.prepared(self.laptop, 'Debugging Methods')
        manifest, members = open_archive(self.archive_of(self.laptop))
        def repack(extra=None, mutate=None):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('home.json', json.dumps(manifest))
                for name, data in members.items():
                    archive.writestr(name, mutate(name, data) if mutate else data)
                if extra: archive.writestr(*extra)
            return buffer.getvalue()
        with self.assertRaisesRegex(ec.Invalid, 'altered'):
            open_archive(repack(mutate=lambda n, d: d + b' ' if n == 'library.json' else d))
        with self.assertRaisesRegex(ec.Invalid, 'unsafe path'):
            open_archive(repack(extra=('../escape.txt', b'x')))
        with self.assertRaisesRegex(ec.Invalid, 'inventory'):
            open_archive(repack(extra=('collections/extra.json', b'{}')))
        with self.assertRaisesRegex(ec.Invalid, 'not a zip'): open_archive(b'plain text')
        empty = self.machine('empty')
        with empty, self.assertRaisesRegex(ec.Invalid, 'nothing saved yet'): backup(empty.project)


if __name__ == '__main__':
    unittest.main()
