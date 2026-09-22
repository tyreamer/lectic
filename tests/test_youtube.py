"""Real journey, synthetic captions; all external yt-dlp calls are mocked."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from capture_store import CaptureStore, capture_command
from ingestors import adapter_for
from ingestors.youtube import YouTubeIngestor
from workflow import compile_workflow
import test_capture as capture_fixtures

VIDEO = 'o64cI6tebnU'
URL = f'https://www.youtube.com/watch?v={VIDEO}&t=868s&list=some-list'
VTT = (b'WEBVTT\nKind: captions\nLanguage: en\n\n00:00:00.000 --> 00:00:05.000\n'
       b'<v Instructor>Before choosing a business idea, ask who has the problem and what they currently do.\n\n'
       b'00:14:28.000 --> 00:14:33.000\nTest one small offer and record what the results do not establish.\n')


def metadata(video=VIDEO):
    return {'id': video, '_type': 'video', 'title': 'Synthetic lesson ' + video,
            'channel': 'Fixture instructor', 'description': 'Never use this description as a transcript.',
            'subtitles': {'en': [{'ext': 'vtt', 'url': 'https://www.youtube.com/api/timedtext'}]},
            'automatic_captions': {'en': [{'ext': 'vtt', 'url': 'https://www.youtube.com/api/timedtext'}]}}


class FakeYtDlp:
    def __init__(self):
        self.commands = []
        self.info = {}
        self.fail = set()
        self.raw = VTT
        self.write_caption = True

    def run(self, command, **kwargs):
        self.commands.append(command)
        assert kwargs['shell'] is False and kwargs['timeout'] == 60
        assert '--skip-download' in command and '--ignore-config' in command
        assert '--no-playlist' in command and '--no-remote-components' in command
        assert not set(command) & {'-x', '--extract-audio', '--download-sections', '--yes-playlist', '--exec', '--cookies-from-browser'}
        video = parse_qs(urlparse(command[-1]).query)['v'][0]
        if video in self.fail:
            return subprocess.CompletedProcess(command, 1, '', 'ERROR: captions unavailable or rate limited')
        if '--dump-single-json' in command:
            info = self.info.get(video, metadata(video))
            return subprocess.CompletedProcess(command, 0, info if isinstance(info, str) else json.dumps(info), '')
        language = command[command.index('--sub-langs') + 1].strip('^$').replace('\\', '')
        extension = command[command.index('--sub-format') + 1]
        if self.write_caption:
            (Path(kwargs['cwd']) / f'caption.{language}.{extension}').write_bytes(self.raw)
        return subprocess.CompletedProcess(command, 0, '', '')


class YouTubeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = isolate_home(self, self.base)
        self.fake = FakeYtDlp()
        self.which = patch('ingestors.youtube.shutil.which', return_value='yt-dlp').start()
        self.boundary = patch('ingestors.youtube.subprocess.run', side_effect=self.fake.run).start()
        self.addCleanup(patch.stopall)

    def test_url_forms_and_playlist_bound(self):
        for url in [URL, f'https://youtu.be/{VIDEO}?t=868', f'https://m.youtube.com/watch?v={VIDEO}',
                    f'youtube.com/watch?v={VIDEO}', f'https://www.youtube.com/shorts/{VIDEO}']:
            self.assertTrue(YouTubeIngestor.accepts(url))
            self.assertEqual(YouTubeIngestor(url).canonical_url, f'https://www.youtube.com/watch?v={VIDEO}')
        for url in ['https://example.com/video', f'https://youtube.com.evil.test/watch?v={VIDEO}',
                    'https://youtube.com/watch?v=bad', f'https://youtube.com@evil.test/watch?v={VIDEO}',
                    f'file://youtube.com/watch?v={VIDEO}']:
            self.assertFalse(YouTubeIngestor.accepts(url))
        with self.assertRaisesRegex(ec.Invalid, 'playlists are not expanded'):
            adapter_for('https://www.youtube.com/playlist?list=500-videos').collect()
        self.assertFalse(self.fake.commands)

    def test_manual_captions_metadata_original_url_and_full_timeline(self):
        record = YouTubeIngestor(URL).collect()[0]
        self.assertEqual(record.raw, VTT)
        self.assertEqual(record.metadata['url'], URL)
        self.assertEqual(record.metadata['caption_type'], 'manual')
        self.assertEqual(record.metadata['creator'], 'Fixture instructor')
        self.assertEqual(record.metadata['title'], 'Synthetic lesson ' + VIDEO)
        segments = ec.normalize(record.raw, '.vtt')
        self.assertEqual(segments[0]['start'], 0)
        self.assertEqual(segments[0]['speaker'], 'Instructor')
        self.assertEqual(segments[1]['start'], 868)
        self.assertIn('--write-subs', self.fake.commands[1])
        self.assertIn('--no-write-auto-subs', self.fake.commands[1])
        self.assertNotIn('&t=', self.fake.commands[0][-1])

    def test_automatic_fallback_and_english_selection(self):
        info = metadata(); info['subtitles'] = {'fr': info['subtitles']['en']}
        info['automatic_captions']['en-orig'] = info['automatic_captions']['en']
        self.fake.info[VIDEO] = info
        record = YouTubeIngestor(URL).collect()[0]
        self.assertEqual(record.metadata['caption_type'], 'automatic')
        self.assertTrue(record.filename.endswith('.en-orig.vtt'))
        self.assertIn('--write-auto-subs', self.fake.commands[1])
        self.assertIn('--no-write-subs', self.fake.commands[1])
        info['subtitles'] = {'en-US': info['automatic_captions']['en']}
        self.assertEqual(YouTubeIngestor(URL).collect()[0].metadata['caption_type'], 'manual')

    def test_srt_fallback_uses_original_bytes(self):
        info = metadata(); info['subtitles']['en'][0]['ext'] = 'srt'; self.fake.info[VIDEO] = info
        self.fake.raw = b'1\n00:00:01,000 --> 00:00:02,000\nAn exact caption.\n'
        record = YouTubeIngestor(URL).collect()[0]
        self.assertTrue(record.filename.endswith('.srt'))
        self.assertEqual(ec.normalize(record.raw, '.srt')[0]['text'], 'An exact caption.')

    def test_unavailable_dependency_is_actionable_and_installs_nothing(self):
        self.which.return_value = None
        with self.assertRaisesRegex(ec.Invalid, 'with your approval'):
            YouTubeIngestor(URL).collect()
        self.boundary.assert_not_called()

    def test_missing_captions_never_substitutes_metadata(self):
        info = metadata(); info['subtitles'] = {}; info['automatic_captions'] = {}
        self.fake.info[VIDEO] = info
        with self.assertRaisesRegex(ec.Invalid, 'No usable English captions'):
            YouTubeIngestor(URL).collect()
        self.assertEqual(len(self.fake.commands), 1)

    def test_malformed_metadata_wrong_video_missing_and_empty_output(self):
        for info in ['not JSON', [], {'id':'different'}, {**metadata(), 'subtitles': ['bad']},
                     {**metadata(), '_type':'playlist', 'entries':[]}]:
            self.fake.info[VIDEO] = info
            with self.subTest(info=info), self.assertRaises(ec.Invalid): YouTubeIngestor(URL).collect()
        self.fake.info.clear(); self.fake.write_caption = False
        with self.assertRaisesRegex(ec.Invalid, 'did not return'): YouTubeIngestor(URL).collect()
        self.fake.write_caption = True; self.fake.raw = b''
        with self.assertRaisesRegex(ec.Invalid, 'empty'): YouTubeIngestor(URL).collect()

    def test_dependency_failure_timeout_and_no_audio_fallback(self):
        self.fake.fail.add(VIDEO)
        with self.assertRaisesRegex(ec.Invalid, 'rate limited'): YouTubeIngestor(URL).collect()
        self.assertEqual(len(self.fake.commands), 1)
        self.boundary.side_effect = subprocess.TimeoutExpired('yt-dlp', 60)
        with self.assertRaisesRegex(ec.Invalid, 'timed out'): YouTubeIngestor(URL).collect()

    def test_direct_compile_acquires_once_and_validates_canonical_sources(self):
        result = compile_workflow(URL, project=self.base)
        self.assertEqual(result['phase'], 'extract')
        self.assertEqual(len(self.fake.commands), 2)  # One metadata probe plus one caption request.
        _, docs, _ = ec.validate_sources(result['run'])
        doc = next(iter(docs.values()))
        self.assertEqual(doc['url'], URL)
        self.assertEqual((Path(result['run']) / doc['raw_path']).read_bytes(), VTT)


class YouTubeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.helper = capture_fixtures.CaptureTests('runTest')
        self.helper.setUp(); self.addCleanup(self.helper.tearDown)
        self.fake = FakeYtDlp()
        self.which = patch('ingestors.youtube.shutil.which', return_value='yt-dlp').start()
        self.boundary_patch = patch('ingestors.youtube.subprocess.run', side_effect=self.fake.run)
        self.boundary_patch.start(); self.addCleanup(patch.stopall)

    def test_eight_link_user_journey_to_validated_build_and_fresh_session(self):
        h = self.helper; case = ec.read(ec.ROOT / 'fixtures/youtube/entrepreneurship.json')
        for url in case['urls']: h.capture(url=url, note=case['context'], collections=[case['collection']])
        h.imported(); self.assertEqual(self.fake.commands, [])
        self.assertTrue(all(r['processing_status']=='awaiting_retrieval' for r in h.rows()))
        result = capture_command(project=h.project, action='process', collection=case['collection'])
        self.assertEqual(result['phase'], 'extract'); self.assertEqual(len(self.fake.commands), 16)
        self.assertTrue(all(r['processing_status']=='partially_processed' for r in h.rows()))
        self.assertTrue(all(r['retrieval_state']['status']=='retrieved' for r in h.rows()))
        _, docs, _ = ec.validate_sources(result['run']); self.assertEqual(len(docs), 8)
        for doc in docs.values():
            self.assertEqual((Path(result['run'])/doc['raw_path']).read_bytes(), VTT)
            self.assertEqual(doc['segments'][0]['start'], 0)
            self.assertIn(doc['url'], case['urls'])
            self.assertNotIn(case['context'], json.dumps(doc))
        h.seed(case['collection'])
        self.assertTrue(all(r['processing_status']=='processed' for r in h.rows()))
        self.assertNotIn(case['context'], (Path(result['run'])/'ir.json').read_text(encoding='utf-8'))
        build = h.finish(case); original_build = (build/'manifest.json').read_bytes()
        self.assertIn(case['context'], (build/'brief.json').read_text(encoding='utf-8'))
        trace = h.store.trace(build)
        self.assertEqual({c['original_value'] for c in trace['captures']}, set(case['urls']))
        h.imported(); h.store.process(case['collection'])
        self.assertEqual(len(self.fake.commands), 16)
        self.boundary_patch.stop()  # Fresh CLI must work from cached bytes without yt-dlp installed.
        fresh = subprocess.run([sys.executable, '-B', str(ec.ROOT/'scripts/ec.py'), 'capture',
                                '--project', str(h.project), '--action', 'process', '--collection', case['collection']],
                               capture_output=True, text=True)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertEqual(json.loads(fresh.stdout)['phase'], 'knowledge_saved')
        self.assertEqual((build/'manifest.json').read_bytes(), original_build)

    def test_failed_link_does_not_block_success_and_retry_clears_error(self):
        h = self.helper
        h.capture(url=URL, collections=['Mixed']); h.capture(url='https://youtu.be/VjVSXJBdlNU', collections=['Mixed'])
        self.fake.fail.add(VIDEO); h.imported()
        self.assertEqual(h.store.process('Mixed')['phase'], 'extract')
        rows = {r['url']: r for r in h.rows()}
        self.assertEqual(rows[URL]['processing_status'], 'needs_attention')
        self.assertEqual(rows[URL]['retrieval_state']['status'], 'unavailable')
        self.assertEqual(rows[URL]['source_ids'], [])
        self.assertEqual(len(ec.validate_sources(h.source_run('Mixed'))[1]), 1)
        self.fake.fail.clear(); h.store.process('Mixed')
        self.assertEqual(len(ec.validate_sources(h.source_run('Mixed'))[1]), 2)
        self.assertFalse(any(r['issues'] for r in h.rows()))
        self.assertTrue(all(r['retrieval_state']['status']=='retrieved' for r in h.rows()))

    def test_url_variants_share_source_and_keep_each_exact_capture(self):
        h = self.helper
        h.capture(url=URL, note='My personal context', collections=['First'])
        other=f'https://youtu.be/{VIDEO}?t=1&si=original-token'
        h.capture(url=other, note='Not my policy', collections=['Second']); h.imported()
        h.store.process('First'); h.seed('First'); h.store.process('Second')
        self.assertEqual(len(self.fake.commands), 2)
        a,b=h.rows('First')[0],h.rows('Second')[0]
        self.assertEqual(a['source_ids'], b['source_ids'])
        self.assertEqual(a['retrieval_state']['original_url'], URL)
        self.assertEqual(b['retrieval_state']['original_url'], other)
        self.assertEqual(a['retrieval_state']['canonical_url'], b['retrieval_state']['canonical_url'])

    def test_unavailable_dependency_retains_all_urls_without_sources(self):
        h=self.helper; self.which.return_value=None
        h.capture(url=URL, collections=['Missing dependency']); h.imported()
        result=h.store.process('Missing dependency')
        self.assertEqual(result['phase'], 'needs_sources')
        self.assertEqual(h.rows()[0]['source_ids'], [])
        self.assertIn('yt-dlp', h.rows()[0]['issues'][0])
        self.assertEqual(self.fake.commands, [])

    def test_download_is_not_processed_and_malformed_captions_have_no_evidence(self):
        h=self.helper; self.fake.raw=b'<html>This is not a transcript</html>'
        h.capture(url=URL, collections=['Malformed']); h.imported(); h.store.process('Malformed')
        row=h.rows()[0]
        self.assertEqual(row['retrieval_state']['status'],'retrieved')
        self.assertEqual(row['processing_status'],'needs_attention')
        self.assertEqual(row['source_ids'],[])
        self.assertFalse(list(h.home.rglob('ir.json')))

    def test_resume_after_normalization_failure_reuses_acquired_bytes(self):
        h=self.helper
        h.capture(url=URL, collections=['Resume']); h.imported()
        with patch.object(h.store, 'canonical_source', side_effect=OSError('Temporary file lock')):
            h.store.process('Resume')
        self.assertEqual(h.rows()[0]['processing_status'], 'needs_attention')
        self.assertEqual(h.rows()[0]['retrieval_state']['status'], 'retrieved')
        self.assertEqual(h.rows()[0]['source_ids'], [])
        self.assertEqual(h.store.process('Resume')['phase'], 'extract')
        self.assertEqual(len(self.fake.commands), 2)
        self.assertEqual(len(h.rows()[0]['source_ids']), 1)
        self.assertFalse(h.rows()[0]['issues'])

    def test_cache_integrity_failure_does_not_create_evidence_or_refetch(self):
        h=self.helper
        h.capture(url=URL, collections=['Integrity']); h.imported()
        with patch.object(h.store, 'canonical_source', side_effect=OSError('Temporary file lock')):
            h.store.process('Integrity')
        receipt=ec.read(next((h.store.root/'retrievals').glob('*.json')))
        blob=h.store.store.blob_path(receipt['records'][0]['blob_hash'])
        blob.write_bytes(b'Changed caption bytes')
        result=h.store.process('Integrity')
        self.assertEqual(result['phase'], 'needs_sources')
        self.assertEqual(h.rows()[0]['source_ids'], [])
        self.assertIn('modified', h.rows()[0]['issues'][0])
        self.assertEqual(len(self.fake.commands), 2)
        state_path=next((h.store.root/'state').glob('capture-*.json'))
        state=ec.read(state_path); state['retrieval']['error']=None; ec.write(state_path,state)
        with self.assertRaisesRegex(ec.Invalid, 'Malformed unavailable retrieval state'):
            h.rows()

    def test_unrelated_urls_and_playlist_are_not_expanded(self):
        h=self.helper
        for url in ['https://example.com/talk','https://www.youtube.com/playlist?list=500-videos']:
            h.capture(url=url,collections=['Unsupported'])
        h.imported(); h.store.process('Unsupported')
        self.assertEqual(self.fake.commands, [])
        self.assertTrue(all(not r['source_ids'] for r in h.rows()))


if __name__ == '__main__':
    unittest.main()
