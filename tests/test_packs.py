"""A pack carries compiled knowledge to another home and is verified there against that person's own copy of the sources."""
import functools
import http.server
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from demo import build
from goal_workflow import work
from ingestors import TranscriptInput
from library_guide import library_view
from packs import build_pack, inspect_pack, install_pack, open_pack

VIDEO_A, VIDEO_B = 'o64cI6tebnU', 'dQw4w9WgXcQ'


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.oracle = build(self.base / 'oracle')
        self.author = self.base / 'author'; self.author.mkdir()
        self.home = isolate_home(self, self.base, 'author-home')

    # ---- helpers
    def seed(self, run):
        """Authored checkpoints stand in for the author's reasoning, matched by content, re-bound to this run."""
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def prepared_collection(self, name, inputs, metadata=None):
        folder = self.author / ('input-' + ec.digest(name.encode())[:6]); folder.mkdir()
        for filename, source in inputs.items(): shutil.copy(source, folder / filename)
        meta = None
        if metadata:
            meta = folder.parent / (folder.name + '.json'); ec.write(meta, metadata)
        result = work(project=self.author, input=str(folder), metadata=str(meta) if meta else None, name=name, action='save')
        self.seed(result['run'])
        result = work(project=self.author, collection=name, action='prepare', reconciled=True)
        self.assertEqual(result['phase'], 'knowledge_saved')
        return result

    def other_home(self, name):
        project = self.base / name; project.mkdir()
        return project, isolate_home(self, self.base, name + '-home')

    # ---- tests
    def test_pack_with_sources_installs_verified_into_another_home_and_is_usable_there(self):
        self.prepared_collection('Debugging Methods', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        (self.base / 'out').mkdir()
        packed = build_pack(self.author, 'Debugging Methods', self.base / 'out', include_sources=True)
        pack = Path(packed['pack'])
        self.assertEqual((pack.name, packed['sources_included'], packed['sources']), ('debugging-methods.lectic', True, 1))
        self.assertGreater(packed['units'], 0)
        info = inspect_pack(str(pack))
        self.assertEqual(info['name'], 'Debugging Methods'); self.assertIn('# Debugging Methods', info['readme']); self.assertIn('lectic install', info['readme'])
        with zipfile.ZipFile(pack) as archive:
            names = set(archive.namelist())
        self.assertTrue({'pack.json', 'README.md', 'knowledge/ir.json', 'knowledge/reconciliation.json', 'sources/excerpts.json'} <= names)
        self.assertTrue(any(n.startswith('sources/raw/') for n in names))

        project, home = self.other_home('reader')
        report = install_pack(project, str(pack))
        self.assertEqual((report['verification'], report['sources_verified'], report['units_dropped']), ('verified', 1, []))
        self.assertTrue(report['knowledge_matches_pack']); self.assertEqual(report['reconciliation'], 'carried from the pack')
        self.assertEqual(report['units_installed'], packed['units'])
        summary = work(project=project, collection='Debugging Methods', action='inspect')['summary']
        self.assertEqual(summary['knowledge_units'], packed['units'])
        # The recipient's knowledge is identical, verified against their own copy of the source, and goal work can start at once.
        row = library_view(project)['collections'][0]
        self.assertEqual(row['knowledge_status'], 'processed'); self.assertEqual(row['pack']['verification'], 'verified')
        self.assertTrue(Path(row['pack']['readable']).is_file())
        self.assertNotEqual(work(project=project, collection='Debugging Methods', action='explore')['phase'], 'reconcile')
        # Installing again does not clobber: the second copy gets a distinct name.
        self.assertEqual(install_pack(project, str(pack))['collection'], 'Debugging Methods (2)')
        self.assertFalse(list(self.home.rglob('reader*')))  # nothing leaked into the author's home

    def test_links_only_pack_retrieves_and_verifies_on_the_installers_network(self):
        photo = ec.ROOT / 'fixtures/photography/photography.vtt'; debug = ec.ROOT / 'fixtures/debugging/debugging.srt'
        names = {f'youtube-{VIDEO_A}.en.vtt': photo, f'youtube-{VIDEO_B}.en.srt': debug}
        metadata = {n: {'url': f'https://www.youtube.com/watch?v={v}', 'title': t, 'caption_type': 'manual'}
                    for n, v, t in ((f'youtube-{VIDEO_A}.en.vtt', VIDEO_A, 'Portrait sharpness'), (f'youtube-{VIDEO_B}.en.srt', VIDEO_B, 'Debugging'))}
        self.prepared_collection('FC Tactics', names, metadata)
        packed = build_pack(self.author, 'FC Tactics', self.base / 'fc.lectic')
        self.assertFalse(packed['sources_included']); self.assertIn('redistribution', packed['share_note'])
        with zipfile.ZipFile(packed['pack']) as archive:
            self.assertFalse(any(n.startswith('sources/raw/') for n in archive.namelist()))

        class Acquired:
            def __init__(self, records): self.records, self.receipt = records, {}
        def retriever(adapter, root, store, *, changed=()):
            video = adapter.canonical_url.rsplit('=', 1)[1]
            filename, source = next((n, s) for n, s in names.items() if video in n)
            raw = source.read_bytes() if video not in changed else b'WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nCaptions were regenerated\n'
            return Acquired([TranscriptInput(filename, raw, {})])

        project, home = self.other_home('fan')
        report = install_pack(project, packed['pack'], retriever=retriever)
        self.assertEqual((report['verification'], report['sources_verified'], report['sources_total']), ('verified', 2, 2))
        self.assertTrue(report['knowledge_matches_pack'])
        self.assertEqual(work(project=project, collection='FC Tactics', action='inspect')['summary']['knowledge_units'], packed['units'])

        # A caption track that changed since packing cannot vouch for its units: they drop, and the report says so.
        project2, _ = self.other_home('later')
        report = install_pack(project2, packed['pack'], retriever=functools.partial(retriever, changed={VIDEO_A}))
        self.assertEqual((report['verification'], report['sources_verified']), ('partial', 1))
        self.assertIn('changed since it was packed', report['sources_unavailable'][0]['reason'])
        self.assertTrue(report['units_dropped']); self.assertLess(report['units_installed'], report['units_in_pack'])
        self.assertFalse(report['knowledge_matches_pack']); self.assertIn('needed', report['reconciliation'])
        self.assertEqual(work(project=project2, collection='FC Tactics', action='inspect')['summary']['knowledge_units'], report['units_installed'])
        self.assertEqual(work(project=project2, collection='FC Tactics', action='prepare')['phase'], 'reconcile')

        # Without any way to obtain a source, nothing is installed and the reason is spelled out.
        project3, _ = self.other_home('offline')
        def offline(adapter, root, store): raise ec.Invalid('yt-dlp is not installed')
        with self.assertRaisesRegex(ec.Invalid, 'could be obtained.*yt-dlp is not installed'):
            install_pack(project3, packed['pack'], retriever=offline)
        self.assertEqual(work(project=project3, action='list')['collections'], [])

    def test_local_files_without_links_need_include_sources(self):
        self.prepared_collection('Private Notes', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        packed = build_pack(self.author, 'Private Notes', self.base / 'notes.lectic')
        project, _ = self.other_home('colleague')
        with self.assertRaisesRegex(ec.Invalid, 'no link to retrieve it from'):
            install_pack(project, packed['pack'])

    def test_altered_or_unsafe_packs_are_refused(self):
        self.prepared_collection('Debugging Methods', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack = Path(build_pack(self.author, 'Debugging Methods', self.base / 'p.lectic', include_sources=True)['pack'])
        raw = pack.read_bytes()
        manifest, members = open_pack(raw)
        tampered = io.BytesIO()
        with zipfile.ZipFile(tampered, 'w') as archive:
            archive.writestr('pack.json', json.dumps(manifest))
            for name, data in members.items():
                if name != 'pack.json': archive.writestr(name, data + b' ' if name == 'knowledge/ir.json' else data)
        with self.assertRaisesRegex(ec.Invalid, 'altered'): open_pack(tampered.getvalue())
        unsafe = io.BytesIO()
        with zipfile.ZipFile(unsafe, 'w') as archive:
            archive.writestr('pack.json', json.dumps(manifest)); archive.writestr('../escape.txt', b'x')
        with self.assertRaisesRegex(ec.Invalid, 'unsafe path'): open_pack(unsafe.getvalue())
        with self.assertRaisesRegex(ec.Invalid, 'not a zip'): open_pack(b'plain text')
        work(project=self.author, input=str(ec.ROOT / 'fixtures/photography'), name='Raw', action='save')
        with self.assertRaisesRegex(ec.Invalid, 'Prepare the collection first'): build_pack(self.author, 'Raw')

    def test_pack_installs_from_a_link(self):
        self.prepared_collection('Debugging Methods', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        served = self.base / 'served'; served.mkdir()
        build_pack(self.author, 'Debugging Methods', served / 'debugging.lectic', include_sources=True)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(served))
        handler.log_message = lambda *args, **kwargs: None
        httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)
        project, _ = self.other_home('web')
        report = install_pack(project, f'http://127.0.0.1:{httpd.server_address[1]}/debugging.lectic')
        self.assertEqual(report['verification'], 'verified')
        with self.assertRaisesRegex(ec.Invalid, 'https'):
            install_pack(project, 'http://example.com/pack.lectic')


if __name__ == '__main__':
    unittest.main()
