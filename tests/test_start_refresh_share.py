"""`start`, `share-artifact`, `refresh` and `diff`: a first run, a static page, and safe re-reading."""
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import cli
import ec
from collection_store import Library
from demo import build
from goal_workflow import work

DEBUGGING = ec.ROOT / 'fixtures/transcripts/debugging.srt'
PHOTOGRAPHY = ec.ROOT / 'fixtures/transcripts/photography.vtt'


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'project'; self.project.mkdir()
        self.home = isolate_home(self, self.base)
        self.material = self.base / 'material'; self.material.mkdir()
        shutil.copy(DEBUGGING, self.material / 'debugging.srt')
        patch('cli.os.getcwd', return_value=str(self.project)).start(); self.addCleanup(patch.stopall)
        patch('cli.checked_clients', return_value={'Claude Code': 'not connected'}).start()

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out): code = cli.main(list(args))
        return code, out.getvalue()

    def seed(self, run):
        """Authored fixture knowledge stands in for the assistant's reasoning, bound to this run."""
        corpus, docs, _ = ec.validate_sources(run)
        by_name = {d['filename']: d for d in docs.values()}
        parts = {sid: [] for sid in docs}
        for spec in ec.read(ec.ROOT / 'fixtures/demo_knowledge.json'):
            refs = [spec] + spec.get('extra_evidence', [])
            if any(ref['filename'] not in by_name for ref in refs): continue
            evidence, attribution = [], []
            for ref in refs:
                source = by_name[ref['filename']]
                segment = source['segments'][ref['segment'] - 1]
                evidence.append({'source_id': source['source_id'], 'segment_id': segment['segment_id'], 'quote': segment['text']})
                who = segment['speaker'] or source['creator']
                attribute = {'source_id': source['source_id'], 'name': who}
                if who and attribute not in attribution: attribution.append(attribute)
            parts[by_name[spec['filename']]['source_id']].append({
                'schema_version': ec.VERSION, 'unit_id': spec['unit_id'], 'type': spec['type'],
                'status': spec.get('status', 'explicit'), 'title': spec['unit_id'].replace('-', ' ').capitalize(),
                'statement': spec['statement'], 'scope': 'Synthetic teaching material authored for tests.',
                'derivation': spec.get('derivation', ''), 'evidence': evidence, 'attribution': attribution,
                'relations': spec.get('relations', [])})
        for sid, units in parts.items():
            ec.write(Path(run) / f'units/{sid}.json', {'schema_version': ec.VERSION, 'corpus_id': corpus['corpus_id'],
                     'source_id': sid, 'note': 'Authored test checkpoint, not automatic extraction.', 'units': units})

    def prepared(self, name, folder, metadata=None):
        meta = None
        if metadata:
            meta = self.base / (ec.digest(name.encode())[:8] + '-meta.json'); ec.write(meta, metadata)
        saved = work(project=self.project, input=str(folder), metadata=str(meta) if meta else None, name=name, action='save')
        self.seed(saved['run'])
        result = work(project=self.project, collection=name, action='prepare', reconciled=True)
        self.assertEqual(result['phase'], 'knowledge_saved', result)
        return result


class StartTests(Base):
    def test_start_saves_a_folder_and_reports_what_to_do_next(self):
        code, out = self.run_cli('start', str(self.material), '--name', 'Field Notes', '--yes')
        self.assertEqual(code, 0, out)
        self.assertIn('a collection named Field Notes', out)
        self.assertIn('debugging.srt', out)
        self.assertIn('No reusable knowledge yet', out)  # honest: saving is not learning
        self.assertIn('Prepare my Field Notes collection', out)
        self.assertIn('lectic share-artifact "Field Notes"', out)
        self.assertIn('lectic pack "Field Notes"', out)
        self.assertEqual([c['name'] for c in Library(self.project).index['collections']], ['Field Notes'])

    def test_start_accepts_one_file_and_names_the_collection_after_it(self):
        code, out = self.run_cli('start', str(self.material / 'debugging.srt'), '--goal',
                                 'review experiments before I run them', '--yes', '--json')
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertEqual((result['mode'], result['collection'], result['source_count']), ('saved', 'Debugging Sources', 1))
        self.assertEqual(result['desired_use'], 'review experiments before I run them')
        self.assertIn('use it to review experiments before I run them', result['next_prompt'])
        self.assertEqual(result['refresh_command'],
                         f'lectic refresh "Debugging Sources" --from "{self.material / "debugging.srt"}"')
        self.assertTrue(Path(result['location']).is_dir())

    def test_start_reuses_an_inferred_folder_name(self):
        source = self.project / 'field-notes'
        source.mkdir()
        shutil.copy(DEBUGGING, source / 'debugging.srt')
        self.assertEqual(self.run_cli('start', 'field-notes', '--yes')[0], 0)
        code, out = self.run_cli('start', 'field-notes', '--yes', '--json')
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)['collection'], 'Field Notes Sources')
        self.assertEqual(len(Library(self.project).index['collections']), 1)

    def test_flag_value_equal_to_source_is_not_removed(self):
        self.assertEqual(cli.positional(['notes', '--name', 'notes'], {'--name'}), ['notes'])

    def test_start_can_be_cancelled_without_a_traceback(self):
        terminal = SimpleNamespace(isatty=lambda: True)
        with patch.object(cli.sys, 'stdin', terminal), patch('builtins.input', side_effect=KeyboardInterrupt):
            code, out = self.run_cli('start')
        self.assertEqual(code, 130)
        self.assertIn('Start cancelled', out)

    def test_interactive_start_with_a_source_still_asks_for_its_use(self):
        terminal = SimpleNamespace(isatty=lambda: True)
        with patch.object(cli.sys, 'stdin', terminal), patch('builtins.input',
                return_value='review experiments before I run them') as prompt:
            code, out = self.run_cli('start', str(self.material / 'debugging.srt'))
        self.assertEqual(code, 0, out)
        self.assertEqual(prompt.call_count, 1)
        self.assertIn('use it to review experiments before I run them', out)

    def test_youtube_links_get_a_plain_default_name(self):
        from start import suggested_name
        self.assertEqual(suggested_name(self.project, 'https://www.youtube.com/watch?v=abc'), 'YouTube Sources')

    def test_start_adds_to_a_collection_that_already_exists(self):
        self.run_cli('start', str(self.material), '--name', 'Field Notes', '--yes')
        shutil.copy(PHOTOGRAPHY, self.material / 'photography.vtt')
        code, out = self.run_cli('start', str(self.material), '--name', 'field notes', '--yes', '--json')
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertEqual(result['source_count'], 2)
        self.assertEqual(len(Library(self.project).index['collections']), 1)

    def test_start_without_material_shows_the_offline_sample(self):
        sample = SimpleNamespace(try_starter=lambda project: {
            'collection': 'Debugging Starter', 'first_result': 'a review of a sample plan',
            'second_result': 'a reusable checklist', 'reuse': {'reused_units': ['a', 'b', 'c']},
            'example_type': 'prewritten synthetic teaching example; no model call',
            'next_prompt': 'Use my Debugging Starter to review this debugging plan'})
        with patch.dict(sys.modules, {'starter': sample}):
            code, out = self.run_cli('start', '--yes')
        self.assertEqual(code, 0, out)
        self.assertIn('Debugging Starter', out)
        self.assertIn('3 saved knowledge units were applied', out)
        self.assertIn('no model call', out)

    def test_start_refuses_a_file_it_cannot_read_without_guessing(self):
        unsupported = self.material / 'diagram.png'; unsupported.write_bytes(b'\x89PNG')
        code, out = self.run_cli('start', str(unsupported), '--yes')
        self.assertEqual(code, 1)
        self.assertIn('.txt, .md, .vtt and .srt', out)


class ShareArtifactTests(Base):
    def test_page_is_one_self_contained_file_describing_the_collection(self):
        self.prepared('Debugging Methods', self.material)
        code, out = self.run_cli('share-artifact', 'Debugging Methods', '--out', str(self.base / 'page.html'))
        self.assertEqual(code, 0, out)
        page = (self.base / 'page.html').read_text(encoding='utf-8')
        self.assertTrue(page.startswith('<!doctype html>'))
        self.assertIn('<h1>Debugging Methods</h1>', page)
        self.assertIn('What it knows', page)
        self.assertIn('Provenance', page)
        self.assertIn('lectic install &quot;debugging-methods.lectic&quot;', page)
        # Self-contained: no scripts, no external resources.
        self.assertNotIn('<script', page.lower())
        for marker in ('src=', 'http-equiv', '<link'): self.assertNotIn(marker, page)
        units = ec.validate_ir(Path(self.prepared_run()))['units']
        self.assertIn(units[0]['statement'], page)

    def prepared_run(self):
        library = Library(self.project)
        folder, data = library.resolve('Debugging Methods')
        return library.run(folder, data)

    def test_page_escapes_source_text_and_refuses_unsafe_links(self):
        self.prepared('Debugging Methods', self.material,
                      {'debugging.srt': {'title': '<script>alert("x")</script>', 'creator': 'A & B'}})
        code, out = self.run_cli('share-artifact', 'Debugging Methods', '--out', str(self.base / 'page.html'))
        self.assertEqual(code, 0, out)
        page = (self.base / 'page.html').read_text(encoding='utf-8')
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', page)
        self.assertNotIn('<script>alert', page)
        self.assertIn('A &amp; B', page)
        from artifact_page import safe_url
        for unsafe in ('javascript:alert(1)', 'file:///etc/passwd', 'data:text/html,x', '', None, 'https://'):
            self.assertIsNone(safe_url(unsafe))
        self.assertEqual(safe_url('https://example.com/a'), 'https://example.com/a')

    def test_page_shows_reusable_methods_but_never_the_private_goal_or_result(self):
        from starter import example_result
        self.prepared('Debugging Methods', self.material)
        completed = example_result(self.project, 'Debugging Methods')
        secret = ec.read(Path(completed['build']) / 'brief.json')['work']['text']
        code, out = self.run_cli('share-artifact', 'Debugging Methods', '--json')
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertEqual(report['methods'], 1)
        page = Path(report['file']).read_text(encoding='utf-8')
        self.assertIn('What it can help with', page)
        self.assertIn('Give it', page)
        self.assertNotIn(secret, page)
        self.assertNotIn('Review a sample debugging plan', page)  # the brief's objective stays private
        self.assertNotIn(str(self.home), page)  # no local paths leak into a shared file

    def test_page_can_omit_quotes_while_retaining_source_provenance(self):
        self.prepared('Debugging Methods', self.material)
        run = Path(self.prepared_run())
        quote = ec.validate_ir(run)['units'][0]['evidence'][0]['quote']
        code, out = self.run_cli('share-artifact', 'Debugging Methods', '--no-quotes',
                                 '--out', str(self.base / 'page.html'))
        self.assertEqual(code, 0, out)
        page = (self.base / 'page.html').read_text(encoding='utf-8')
        self.assertNotIn(quote, page)
        self.assertIn('quoted excerpts were omitted', page)
        self.assertIn('Evidence: debugging.srt', page)

    def test_unknown_collection_is_reported_not_guessed(self):
        code, out = self.run_cli('share-artifact', 'Nothing Saved')
        self.assertEqual(code, 1)
        self.assertIn('Collection name is missing', out)
        self.assertEqual(self.run_cli('share-artifact')[0], 2)


class RefreshTests(Base):
    def test_refresh_requires_an_explicit_source_and_never_infers_one(self):
        self.prepared('Debugging Methods', self.material)
        code, out = self.run_cli('refresh', 'Debugging Methods')
        self.assertEqual(code, 2)
        self.assertIn('never guesses', out)

    def test_identical_material_reports_no_change_and_writes_no_new_revision(self):
        self.prepared('Debugging Methods', self.material)
        before = Library(self.project).inspect('Debugging Methods')
        code, out = self.run_cli('refresh', 'Debugging Methods', '--from', str(self.material))
        self.assertEqual(code, 0, out)
        self.assertIn('Nothing changed', out)
        after = Library(self.project).inspect('Debugging Methods')
        self.assertEqual(after['active_revision'], before['active_revision'])
        self.assertEqual(after['source_revisions'], before['source_revisions'])
        self.assertEqual(after['knowledge_units'], before['knowledge_units'])

    def test_changed_material_adds_a_revision_and_keeps_the_previous_one(self):
        self.prepared('Debugging Methods', self.material)
        before = Library(self.project).inspect('Debugging Methods')
        (self.material / 'debugging.srt').write_text(
            (self.material / 'debugging.srt').read_text(encoding='utf-8') +
            '\n99\n00:09:59,000 --> 00:10:00,000\nA newly recorded closing line.\n', encoding='utf-8')
        shutil.copy(PHOTOGRAPHY, self.material / 'photography.vtt')
        code, out = self.run_cli('refresh', 'Debugging Methods', '--from', str(self.material), '--json')
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertFalse(report['unchanged'])
        self.assertEqual(report['changed_sources'], ['debugging.srt'])
        self.assertEqual(report['added_sources'], ['photography.vtt'])
        self.assertEqual(report['removed_sources'], [])
        self.assertTrue(report['rebuild_needed'])
        self.assertIn('Prepare my Debugging Methods collection', report['message'])
        after = Library(self.project).inspect('Debugging Methods')
        self.assertEqual(after['source_revisions'], before['source_revisions'] + 1)
        # The earlier revision and its knowledge are still readable.
        library = Library(self.project)
        folder, data = library.resolve('Debugging Methods')
        previous = ec.safe_child(folder, next(r['run'] for r in data['revisions'] if r['revision_id'] == before['active_revision']))
        self.assertEqual(len(ec.validate_ir(previous)['units']), before['knowledge_units'])

    def test_folder_refresh_removes_missing_sources_but_keeps_history(self):
        shutil.copy(PHOTOGRAPHY, self.material / 'photography.vtt')
        self.prepared('Mixed Methods', self.material)
        before = Library(self.project).inspect('Mixed Methods')
        (self.material / 'photography.vtt').unlink()
        code, out = self.run_cli('refresh', 'Mixed Methods', '--from', str(self.material), '--json')
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertEqual(report['removed_sources'], ['photography.vtt'])
        self.assertTrue(report['pruned_missing_sources'])
        after = Library(self.project).inspect('Mixed Methods')
        self.assertEqual(after['source_count'], 1)
        self.assertEqual(after['source_revisions'], before['source_revisions'] + 1)
        library = Library(self.project)
        folder, data = library.resolve('Mixed Methods')
        previous = ec.safe_child(folder, next(r['run'] for r in data['revisions']
                                              if r['revision_id'] == before['active_revision']))
        self.assertEqual(len(ec.validate_ir(previous)['units']), before['knowledge_units'])

    def test_diff_reads_two_revisions_without_changing_anything(self):
        self.prepared('Debugging Methods', self.material)
        (self.material / 'debugging.srt').write_text(
            (self.material / 'debugging.srt').read_text(encoding='utf-8') +
            '\n99\n00:09:59,000 --> 00:10:00,000\nA newly recorded closing line.\n', encoding='utf-8')
        self.run_cli('refresh', 'Debugging Methods', '--from', str(self.material))
        state = ec.read(Library(self.project).resolve('Debugging Methods')[0] / 'collection.json')
        code, out = self.run_cli('diff', 'Debugging Methods', '--json')
        self.assertEqual(code, 0, out)
        changes = json.loads(out)
        self.assertEqual(changes['changed_sources'], ['debugging.srt'])
    def test_share_with_collection_name_writes_page(self):
        self.prepared('Debugging Methods', self.material)
        code, out = self.run_cli('share', 'Debugging Methods', '--out', str(self.base / 'page2.html'))
        self.assertEqual(code, 0, out)
        self.assertTrue((self.base / 'page2.html').is_file())
        self.assertIn('Wrote a shareable page for Debugging Methods', out)

    def test_prepare_command_reports_and_reconciles(self):
        self.run_cli('start', str(self.material), '--name', 'Prepare Test', '--yes')
        # Initially pending extraction
        code, out = self.run_cli('prepare', 'Prepare Test')
        self.assertEqual(code, 0, out)
        self.assertIn('pending source(s)', out)
        # Seed units
        folder, data = Library(self.project).resolve('Prepare Test')
        run = Library(self.project).run(folder, data)
        self.seed(run)
        # Reconcile and assemble IR
        code, out = self.run_cli('prepare', 'Prepare Test')
        self.assertEqual(code, 0, out)
        self.assertIn('Prepared', out)
        self.assertIn('knowledge units verified', out)


if __name__ == '__main__':
    unittest.main()
