"""Tests for web article extraction, URL normalization, and honest source description."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from capture_policy import _normalize_url, _platform, describe_source
from goal_workflow import work
from ingestors.web import WebArticleIngestor, extract_article_text
from linked_sources import resolver_for


SAMPLE_HTML = b"""<!doctype html>
<html>
<head>
  <title>Understanding Neural Network Pruning - Tech Blog</title>
  <style>body { font-family: sans-serif; }</style>
  <script>console.log("analytics");</script>
</head>
<body>
  <header><nav><a href="/">Home</a></nav></header>
  <article>
    <h1>Understanding Neural Network Pruning</h1>
    <p>Neural network pruning removes non-essential weights from deep learning models to reduce inference cost.</p>
    <h2>Magnitude Pruning</h2>
    <p>Weights below a threshold are replaced with zeros, followed by a fine-tuning phase.</p>
  </article>
  <footer><p>Copyright 2026</p></footer>
</body>
</html>"""


class WebIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'project'
        self.project.mkdir()
        self.home = isolate_home(self, self.base)

    def test_extract_article_text_strips_scripts_and_extracts_markdown(self):
        title, text = extract_article_text(SAMPLE_HTML)
        self.assertIn('Understanding Neural Network Pruning', title)
        self.assertIn('# Understanding Neural Network Pruning', text)
        self.assertIn('Magnitude Pruning', text)
        self.assertNotIn('analytics', text)
        self.assertNotIn('font-family', text)
        self.assertNotIn('Home', text)

    def test_accepts_articles_and_rejects_youtube_and_walled_gardens(self):
        self.assertTrue(WebArticleIngestor.accepts('https://example.com/blog/pruning'))
        self.assertTrue(WebArticleIngestor.accepts('https://substack.com/@author/post'))
        self.assertTrue(WebArticleIngestor.accepts('https://medium.com/post-title'))
        # Rejects YouTube
        self.assertFalse(WebArticleIngestor.accepts('https://www.youtube.com/watch?v=123'))
        self.assertFalse(WebArticleIngestor.accepts('https://youtu.be/123'))
        # Rejects walled gardens
        self.assertFalse(WebArticleIngestor.accepts('https://instagram.com/p/123'))
        self.assertFalse(WebArticleIngestor.accepts('https://www.tiktok.com/@user/video/123'))
        self.assertFalse(WebArticleIngestor.accepts('https://x.com/user/status/123'))

    def test_resolver_for_routes_articles(self):
        adapter = resolver_for('https://example.com/guide')
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.adapter, 'web-article')

    def test_describe_source_honestly_reports_article_text(self):
        source = describe_source(url='https://example.com/post')
        self.assertEqual(source['source_type'], 'web')
        self.assertEqual(source['retrieval'], 'article_text')
        self.assertTrue(source['content_available'])
        self.assertIn('retrieves and cleans the article text', source['what_lectic_gets'])

    def test_scheme_less_urls_are_normalized(self):
        self.assertEqual(_normalize_url('twitter.com/user'), 'https://twitter.com/user')
        self.assertEqual(_platform('twitter.com/user'), 'X')
        self.assertEqual(_platform('medium.com/article'), 'Medium')

    @patch('urllib.request.urlopen')
    def test_ingestor_collects_article_and_saves_to_collection(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = SAMPLE_HTML
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        ingestor = WebArticleIngestor('https://example.com/pruning-guide')
        records = ingestor.collect()
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].filename.endswith('.md'))
        self.assertIn(b'Neural Network Pruning', records[0].raw)

        # Archive through goal_workflow
        res = work(project=self.project, input='https://example.com/pruning-guide',
                   name='Pruning Guide', action='save')
        self.assertEqual(res['phase'], 'archived')
        self.assertEqual(res['transcripts'], 1)


if __name__ == '__main__':
    unittest.main()
