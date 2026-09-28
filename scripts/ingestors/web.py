"""Lightweight, bounded HTML article extraction. Never executes JavaScript or downloads media."""
from dataclasses import dataclass
from html.parser import HTMLParser
import io
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from ec import Invalid, require
from . import TranscriptInput

try:
    from release_version import VERSION
except ImportError:
    try:
        from ..release_version import VERSION
    except ImportError:
        VERSION = '0.3.2'

MAX_ARTICLE_BYTES = 4 * 1024 * 1024  # 4 MB max raw download
MAX_TEXT_CHARS = 200_000             # ~40,000 words max extracted text

STRIP_TAGS = {
    'script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript',
    'svg', 'form', 'button', 'iframe', 'canvas', 'video', 'audio', 'select'
}

BLOCK_TAGS = {
    'p', 'div', 'article', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'li', 'blockquote', 'pre', 'tr', 'td', 'th', 'dt', 'dd', 'hr', 'br'
}


class _ArticleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts = []
        self.in_title = False
        self.ignore_depth = 0
        self.blocks = []
        self._current = []
        self.total_chars = 0

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in STRIP_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth > 0:
            return
        if tag_lower == 'title':
            self.in_title = True
        elif tag_lower in BLOCK_TAGS:
            self._flush_block()
            if tag_lower.startswith('h') and len(tag_lower) == 2 and tag_lower[1].isdigit():
                level = int(tag_lower[1])
                self._current.append('#' * level + ' ')

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in STRIP_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
            return
        if self.ignore_depth > 0:
            return
        if tag_lower == 'title':
            self.in_title = False
        elif tag_lower in BLOCK_TAGS:
            self._flush_block()

    def handle_data(self, data):
        if self.ignore_depth > 0:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        text = data.strip()
        if text:
            if self.total_chars + len(text) > MAX_TEXT_CHARS:
                return
            self._current.append(data)
            self.total_chars += len(text)

    def _flush_block(self):
        if self._current:
            raw = ''.join(self._current)
            cleaned = ' '.join(raw.split())
            if cleaned:
                self.blocks.append(cleaned)
            self._current = []

    def get_title(self):
        return ' '.join(''.join(self.title_parts).split())

    def get_text(self):
        self._flush_block()
        return '\n\n'.join(self.blocks)


def extract_article_text(html_bytes: bytes, encoding: str = 'utf-8') -> tuple[str, str]:
    """Parse HTML and extract clean (title, markdown_content)."""
    text = html_bytes.decode(encoding, errors='replace')
    parser = _ArticleHTMLParser()
    parser.feed(text)
    parser.close()
    title = parser.get_title()
    content = parser.get_text()
    return title, content


def slugify(title: str, max_len: int = 40) -> str:
    cleaned = re.sub(r'[^\w\s-]', '', title.lower()).strip()
    slug = re.sub(r'[-\s]+', '-', cleaned)[:max_len].strip('-')
    return slug or 'article'


class WebArticleIngestor:
    adapter = 'web-article'
    version = '1'

    def __init__(self, url: str):
        self.url = url.strip()
        parts = urllib.parse.urlsplit(self.url)
        self.canonical_url = urllib.parse.urlunsplit(
            (parts.scheme or 'https', parts.netloc.lower().removeprefix('www.'), parts.path, parts.query, '')
        )

    WALLED_GARDENS = {
        'instagram.com', 'tiktok.com', 'facebook.com', 'threads.net',
        'x.com', 'twitter.com'
    }

    @classmethod
    def accepts(cls, location: str) -> bool:
        if not isinstance(location, str):
            return False
        loc = location.strip()
        if not loc.lower().startswith(('http://', 'https://')):
            return False
        host = (urllib.parse.urlsplit(loc).hostname or '').lower()
        if host.startswith('www.'):
            host = host[4:]
        # YouTube is handled by YouTubeIngestor
        if host in {'youtube.com', 'youtu.be'} or host.endswith(('.youtube.com',)):
            return False
        # Walled gardens requiring login/app access remain reference-only
        for garden in cls.WALLED_GARDENS:
            if host == garden or host.endswith('.' + garden):
                return False
        return bool(host and '.' in host)

    def collect(self, metadata=None) -> list[TranscriptInput]:
        req = urllib.request.Request(
            self.canonical_url,
            headers={
                'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Lectic/{VERSION}',
                'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get('Content-Type', '')
                if 'charset=' in content_type.lower():
                    charset = content_type.lower().split('charset=')[-1].split(';')[0].strip()
                else:
                    charset = 'utf-8'
                raw_bytes = resp.read(MAX_ARTICLE_BYTES)
        except Exception as exc:
            raise Invalid(f"Could not retrieve web article from {self.canonical_url}: {exc}") from exc

        title, text = extract_article_text(raw_bytes, encoding=charset)
        if not text.strip():
            raise Invalid(f"Web article at {self.canonical_url} contained no readable text")

        clean_title = title or metadata.get('title') if metadata else None
        if not clean_title:
            host = urllib.parse.urlsplit(self.canonical_url).hostname or 'article'
            clean_title = f"Article from {host}"

        filename = f"{slugify(clean_title)}.md"
        meta = {
            'title': clean_title,
            'creator': urllib.parse.urlsplit(self.canonical_url).hostname or '',
            'url': self.canonical_url,
            'caption_type': 'manual'
        }
        if metadata and isinstance(metadata, dict):
            meta.update({k: v for k, v in metadata.items() if v is not None})

        formatted = f"# {clean_title}\n\nSource: {self.canonical_url}\n\n{text}\n".encode('utf-8')
        return [TranscriptInput(filename=filename, raw=formatted, metadata=meta)]
