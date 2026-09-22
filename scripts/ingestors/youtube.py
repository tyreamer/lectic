"""Optional, bounded YouTube caption acquisition. Never download video or audio."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

from ec import Invalid, require
from . import TranscriptInput


def module_launcher():
    """yt_dlp installed as a module next to Lectic (what `lectic setup` does) needs no PATH entry."""
    try:
        if importlib.util.find_spec('yt_dlp') is not None: return [sys.executable, '-m', 'yt_dlp']
    except (ImportError, ValueError):
        pass
    return None


class YouTubeIngestor:
    adapter = 'youtube-captions'
    version = '1'
    max_caption_bytes = 8 * 1024 * 1024

    def __init__(self, location):
        self.location = str(location)  # Preserve the shared query and timestamp exactly.

    @staticmethod
    def parsed(location):
        value = str(location)
        try:
            url = urlparse(value if '://' in value else 'https://' + value)
            if url.scheme not in {'http', 'https'} or url.username or url.password or url.port:
                return None, None
            query = parse_qs(url.query)
            video = None
            if url.hostname in {'youtu.be', 'www.youtu.be'}:
                video = url.path.strip('/') if url.path.count('/') <= 2 else None
            elif url.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}:
                if url.path == '/watch' and len(query.get('v', [])) == 1:
                    video = query['v'][0]
                elif re.fullmatch(r'/(shorts|embed|live)/[\w-]{11}/?', url.path):
                    video = url.path.strip('/').split('/')[1]
                elif url.path == '/playlist' and query.get('list'):
                    return None, 'playlist'
            return (video, 'video') if video and re.fullmatch(r'[A-Za-z0-9_-]{11}', video) else (None, None)
        except ValueError:
            return None, None

    @classmethod
    def accepts(cls, location):
        return cls.parsed(location)[1] is not None

    @property
    def canonical_url(self):
        video, kind = self.parsed(self.location)
        require(kind != 'playlist', 'YouTube playlists are not expanded. Supply individual video URLs; a watch URL with a playlist parameter processes only that video.')
        require(video, 'Unsupported YouTube video URL')
        return 'https://www.youtube.com/watch?v=' + video

    @staticmethod
    def choose_caption(info):
        """One English track: manual first, then automatic; never live chat."""
        for kind, field in [('manual', 'subtitles'), ('automatic', 'automatic_captions')]:
            tracks = info.get(field) or {}
            require(isinstance(tracks, dict), 'Malformed YouTube caption metadata')
            languages = [key for key in tracks if re.fullmatch(r'en(?:-[A-Za-z0-9]+)*', key)]
            languages.sort(key=lambda key: (0 if key == ('en-orig' if kind == 'automatic' else 'en') else
                                            1 if key == 'en' else 2, key))
            for language in languages:
                formats = tracks[language]
                require(isinstance(formats, list) and all(isinstance(f, dict) for f in formats),
                        'Malformed YouTube caption formats')
                for extension in ['vtt', 'srt']:
                    if any(f.get('ext') == extension and isinstance(f.get('url'), str) and f['url'] for f in formats):
                        return kind, language, extension
        raise Invalid('No usable English captions are available for this YouTube video. The link remains saved; no video, audio, or metadata summary was substituted.')

    @staticmethod
    def launcher():
        """A yt-dlp executable on PATH, or the yt_dlp module in this interpreter (pip-installed)."""
        executable = shutil.which('yt-dlp')
        return [executable] if executable else module_launcher()

    @staticmethod
    def run(command, folder):
        try:
            result = subprocess.run(command, cwd=folder, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=60, shell=False)
        except FileNotFoundError as exc:
            raise Invalid('yt-dlp is unavailable. Install a current yt-dlp executable with your approval, then retry processing the saved collection.') from exc
        except subprocess.TimeoutExpired as exc:
            raise Invalid('YouTube caption retrieval timed out. The link remains saved; retry processing later.') from exc
        except OSError as exc:
            raise Invalid('Could not start yt-dlp: ' + str(exc)) from exc
        if result.returncode:
            detail = ' '.join((result.stderr or result.stdout or 'No diagnostic returned').split())[:800]
            raise Invalid('YouTube caption retrieval failed: ' + detail + ' The link remains saved; retry later or check yt-dlp availability/version.')
        return result.stdout

    def collect(self, metadata=None):
        require(metadata is None, 'YouTube source metadata comes from retrieval; preserve personal annotations in capture notes.')
        canonical = self.canonical_url  # Bound playlists before dependency/network access.
        launcher = self.launcher()
        require(launcher, 'yt-dlp is not installed. Run `lectic setup` to add YouTube support (it asks before installing anything), or `pip install yt-dlp`; then process this collection again. Nothing was installed automatically.')
        common = launcher + ['--ignore-config', '--no-plugin-dirs', '--no-remote-components',
                  '--no-cache-dir', '--no-playlist', '--skip-download', '--ignore-no-formats-error',
                  '--no-progress', '--encoding', 'utf-8', '--socket-timeout', '15',
                  '--retries', '1', '--extractor-retries', '1']
        with tempfile.TemporaryDirectory(prefix='lectic-youtube-') as temporary:
            output = self.run(common + ['--dump-single-json', '--', canonical], temporary)
            require(len(output) <= 16 * 1024 * 1024, 'YouTube metadata exceeds the supported size')
            try:
                info = json.loads(output)
            except (ValueError, TypeError) as exc:
                raise Invalid('Malformed JSON returned by yt-dlp; no source was created') from exc
            require(isinstance(info, dict) and info.get('id') == self.parsed(self.location)[0] and
                    info.get('_type', 'video') == 'video' and 'entries' not in info,
                    'yt-dlp returned an unexpected video or playlist; no source was created')
            kind, language, extension = self.choose_caption(info)
            flags = ['--write-subs', '--no-write-auto-subs'] if kind == 'manual' else ['--write-auto-subs', '--no-write-subs']
            self.run(common + flags + ['--sub-langs', '^' + re.escape(language) + '$',
                                      '--sub-format', extension, '--output', 'caption.%(ext)s', '--', canonical], temporary)
            caption = Path(temporary) / f'caption.{language}.{extension}'
            require(caption.is_file() and not caption.is_symlink(),
                    'yt-dlp did not return the selected caption file. The link remains saved; no source was created.')
            require(0 < caption.stat().st_size <= self.max_caption_bytes, 'Caption file is empty or exceeds the supported size')
            title = info.get('title')
            creator = info.get('channel') or info.get('uploader') or info.get('creator')
            require(title is None or isinstance(title, str), 'Malformed YouTube title')
            require(creator is None or isinstance(creator, str), 'Malformed YouTube creator')
            original = self.location if '://' in self.location else 'https://' + self.location
            return [TranscriptInput(f'youtube-{info["id"]}.{language}.{extension}', caption.read_bytes(),
                                    {'title': title or None, 'creator': creator or None,
                                     'url': original, 'caption_type': kind})]
