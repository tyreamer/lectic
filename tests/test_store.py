"""The store owns every filesystem-only behavior; nothing above it may depend on links, renames or locks."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ec
from store import LocalStore, staged


class LocalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'home'
        self.store = LocalStore(self.root)

    def test_blobs_are_content_addressed_and_verified(self):
        h = self.store.put_blob(b'same bytes')
        self.assertEqual(self.store.put_blob(b'same bytes'), h)
        self.assertEqual(len(list((self.root / 'blobs').iterdir())), 1)
        self.assertEqual(self.store.get_blob(h), b'same bytes')
        self.store.blob_path(h).write_bytes(b'tampered')
        with self.assertRaisesRegex(ec.Invalid, 'modified'): self.store.get_blob(h)
        with self.assertRaisesRegex(ec.Invalid, 'modified'): self.store.put_blob(b'same bytes')
        with self.assertRaisesRegex(ec.Invalid, 'Missing'): self.store.get_blob('0' * 64)
        with self.assertRaisesRegex(ec.Invalid, 'Malformed'): self.store.blob_path('../escape')

    def test_legacy_capture_blob_location_is_still_readable(self):
        legacy = self.root / 'capture' / 'blobs'; legacy.mkdir(parents=True)
        h = ec.digest(b'old capture'); (legacy / h).write_bytes(b'old capture')
        self.assertEqual(self.store.get_blob(h), b'old capture')
        self.assertEqual(self.store.put_blob(b'old capture'), h)
        self.assertFalse((self.root / 'blobs').exists())
        # New bytes go to the canonical location.
        new = self.store.put_blob(b'new capture')
        self.assertTrue((self.root / 'blobs' / new).is_file())

    def test_materialize_falls_back_to_copy_without_hard_links(self):
        h = self.store.put_blob(b'payload')
        linked = self.root / 'snap' / 'raw' / 'a.txt'
        self.store.materialize(h, linked)
        self.assertEqual(linked.read_bytes(), b'payload')
        copied = self.root / 'snap' / 'raw' / 'b.txt'
        with patch('store.os.link', side_effect=OSError('links unsupported')):
            self.store.materialize(h, copied)
        self.assertEqual(copied.read_bytes(), b'payload')
        with self.assertRaisesRegex(ec.Invalid, 'Missing'): self.store.materialize('1' * 64, self.root / 'snap' / 'c.txt')

    def test_staged_publishes_atomically_and_discards_on_error(self):
        destination = self.root / 'runs' / 'one'
        with staged(destination) as staging:
            (staging / 'file.txt').write_text('ready', encoding='utf-8')
            self.assertFalse(destination.exists())
        self.assertEqual((destination / 'file.txt').read_text(encoding='utf-8'), 'ready')
        with self.assertRaises(RuntimeError):
            with staged(self.root / 'runs' / 'two') as staging:
                (staging / 'file.txt').write_text('partial', encoding='utf-8')
                raise RuntimeError('validation failed')
        self.assertFalse((self.root / 'runs' / 'two').exists())
        self.assertEqual({p.name for p in (self.root / 'runs').iterdir()}, {'one'})
        # An identical snapshot published first wins; the later staging is discarded, not merged.
        with staged(destination) as staging:
            (staging / 'file.txt').write_text('other', encoding='utf-8')
        self.assertEqual((destination / 'file.txt').read_text(encoding='utf-8'), 'ready')

    def test_transactions_are_exclusive_per_name(self):
        with self.store.transaction('capture'):
            with self.assertRaisesRegex(ec.Invalid, 'Another capture operation'):
                with LocalStore(self.root).transaction('capture'): pass
            with LocalStore(self.root).transaction('other'): pass
        with LocalStore(self.root).transaction('capture'): pass


if __name__ == '__main__':
    unittest.main()
