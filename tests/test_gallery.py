"""The public gallery stays reproducible and discoverable."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GalleryTests(unittest.TestCase):
    def test_five_journeys_point_to_real_fixtures(self):
        gallery = (ROOT / 'docs/EXAMPLES.md').read_text(encoding='utf-8')
        fixtures = [
            'fixtures/photography/photography.vtt',
            'fixtures/universal/architecture/source.txt',
            'fixtures/universal/education/source.txt',
            'fixtures/opportunities/conflicting/source.txt',
            'fixtures/debugging/debugging.srt',
        ]
        for fixture in fixtures:
            self.assertTrue((ROOT / fixture).is_file(), fixture)
            self.assertIn(fixture, gallery)
        self.assertEqual(gallery.count('### Real use'), 5)
        self.assertTrue('INPUT -> WAYKIT -> ARTIFACT -> REAL USE' in gallery or 'INPUT -> LECTIC -> ARTIFACT -> REAL USE' in gallery)

    def test_gallery_and_beginner_commands_are_discoverable(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        cli = (ROOT / 'docs/CLI.md').read_text(encoding='utf-8')
        site = (ROOT / 'docs/index.html').read_text(encoding='utf-8')
        self.assertIn('[example gallery](docs/EXAMPLES.md)', readme)
        self.assertIn('docs/EXAMPLES.md', site)
        for command in ('start', 'share-artifact', 'refresh', 'diff'):
            self.assertTrue(f'waykit {command}' in readme or f'lectic {command}' in readme)
            self.assertTrue(f'waykit {command}' in cli or f'lectic {command}' in cli)


if __name__ == '__main__':
    unittest.main()