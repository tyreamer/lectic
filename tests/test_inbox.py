from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import threading
import time

from support import isolate_home
import ec
from inbox import ensure_inbox_folder, parse_drop_file, scan_inbox, route_inbox_item, route_all_inbox, watch_inbox
import cli
from lectic_mcp import Server


class InboxDropTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.author = self.base / 'author'
        self.author.mkdir()
        self.home = isolate_home(self, self.base, 'author-home')
        self.inbox_dir = self.base / 'test-inbox'
        os.environ['LECTIC_INBOX_DIR'] = str(self.inbox_dir)

    def tearDown(self):
        os.environ.pop('LECTIC_INBOX_DIR', None)

    def test_ensure_inbox_folder_creates_structure(self):
        folder = ensure_inbox_folder(self.author)
        self.assertTrue(folder.is_dir())
        self.assertTrue((folder / '.processed').is_dir())
        self.assertTrue((folder / '_README.txt').is_file())
        content = (folder / '_README.txt').read_text(encoding='utf-8')
        self.assertIn('Lectic Drop Inbox', content)

    def test_parse_drop_files(self):
        folder = ensure_inbox_folder(self.author)

        # 1. Windows .url file
        url_file = folder / 'Market_Strategy.url'
        url_file.write_text('[InternetShortcut]\nURL=https://www.youtube.com/watch?v=24JAM7BACtA\n', encoding='utf-8')
        parsed_url = parse_drop_file(url_file)
        self.assertEqual(parsed_url['url'], 'https://www.youtube.com/watch?v=24JAM7BACtA')
        self.assertEqual(parsed_url['title'], 'Market Strategy')

        # 2. macOS .webloc plist file
        webloc_file = folder / 'FUT_Trading.webloc'
        webloc_data = {'URL': 'https://youtube.com/watch?v=test1234'}
        webloc_file.write_bytes(plistlib.dumps(webloc_data))
        parsed_webloc = parse_drop_file(webloc_file)
        self.assertEqual(parsed_webloc['url'], 'https://youtube.com/watch?v=test1234')

        # 3. Text file with URL and notes
        txt_file = folder / 'Notes.txt'
        txt_file.write_text('https://youtube.com/watch?v=note123\nGreat breakdown of early cycle trading.', encoding='utf-8')
        parsed_txt = parse_drop_file(txt_file)
        self.assertEqual(parsed_txt['url'], 'https://youtube.com/watch?v=note123')
        self.assertEqual(parsed_txt['text'], 'Great breakdown of early cycle trading.')

    def test_scan_inbox_detects_drops(self):
        folder = ensure_inbox_folder(self.author)
        item1 = folder / 'Pricing_Tactics.url'
        item1.write_text('[InternetShortcut]\nURL=https://www.youtube.com/watch?v=pricing123\n', encoding='utf-8')

        scan = scan_inbox(self.author)
        self.assertEqual(scan['count'], 1)
        self.assertEqual(scan['items'][0]['filename'], 'Pricing_Tactics.url')
        self.assertEqual(scan['items'][0]['url'], 'https://www.youtube.com/watch?v=pricing123')

    def test_route_inbox_item_and_archives(self):
        folder = ensure_inbox_folder(self.author)
        drop = folder / 'My_Clip.url'
        drop.write_text('[InternetShortcut]\nURL=https://www.youtube.com/watch?v=clip123\n', encoding='utf-8')

        report = route_inbox_item(self.author, 'My_Clip.url', collection_name='Trading Tricks')
        self.assertEqual(report['phase'], 'routed')
        self.assertEqual(report['collection'], 'Trading Tricks')

        # File is moved out of active inbox into .processed/
        self.assertFalse(drop.exists())
        self.assertTrue(Path(report['archived_to']).is_file())

        # Scan should now be empty
        scan = scan_inbox(self.author)
        self.assertEqual(scan['count'], 0)

    def test_mcp_inbox_and_library_surfaces_drops(self):
        folder = ensure_inbox_folder(self.author)
        drop = folder / 'Quick_Note.txt'
        drop.write_text('https://example.com/article\nInteresting perspective on software architecture.', encoding='utf-8')

        server = Server(project=str(self.author))

        # 1. tool_library includes inbox_pending
        lib_res = server.tool_library()
        self.assertIn('inbox_pending', lib_res)
        self.assertEqual(lib_res['inbox_count'], 1)

        # 2. tool_inbox lists items
        list_res = server.call('lectic_inbox', {'action': 'list'})
        self.assertFalse(list_res['isError'])
        data = json.loads(list_res['content'][0]['text'])
        self.assertEqual(data['count'], 1)

        # 3. tool_inbox routes items
        route_res = server.call('lectic_inbox', {'action': 'route', 'items': {'Quick_Note.txt': 'Architecture'}})
        self.assertFalse(route_res['isError'])
        rdata = json.loads(route_res['content'][0]['text'])
        self.assertEqual(rdata['processed_count'], 1)
        self.assertEqual(rdata['items'][0]['collection'], 'Architecture')

        # 4. Now library has 0 inbox drops
        lib_after = server.tool_library()
        self.assertNotIn('inbox_pending', lib_after)

    def test_cli_inbox_commands(self):
        folder = ensure_inbox_folder(self.author)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['inbox'])
        self.assertEqual(code, 0)
        self.assertIn('Inbox is empty', buf.getvalue())

        # Add a file
        drop = folder / 'New_Video.url'
        drop.write_text('[InternetShortcut]\nURL=https://youtube.com/watch?v=sample\n', encoding='utf-8')

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['inbox'])
        self.assertEqual(code, 0)
        self.assertIn('1 item waiting', buf.getvalue())
        self.assertIn('New_Video.url', buf.getvalue())

        # Process via CLI
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['inbox', '--process'])
        self.assertEqual(code, 0)
        self.assertIn('Sorted 1 drop item into your collections', buf.getvalue())

    def test_immediate_processing_on_mcp_capture_save(self):
        server = Server(project=str(self.author))
        # Explicit collection immediately processes
        res = server.tool_capture_save(text="Clean Architecture is a software design philosophy.", collections=['Software Design'])
        self.assertEqual(res['phase'], 'captured')
        self.assertEqual(res['decision'], 'explicit')
        self.assertIn('processed', res)

    def test_clarification_flow_then_immediate_processing(self):
        from collection_store import Library
        Library(self.author).archive(name='Backend Architecture')
        Library(self.author).archive(name='Frontend Architecture')

        server = Server(project=str(self.author))
        # Ambiguous target -> needs clarification
        res = server.tool_capture_save(text="Architecture design decisions for microservices.")
        self.assertEqual(res['decision'], 'needs_clarification')
        self.assertTrue(res['question'])
        cid = res['capture_id']

        # User clarifies: move to Backend Architecture -> immediately processes
        move_res = server.tool_capture(action='move', items=[cid], to=['Backend Architecture'])
        self.assertEqual(move_res['phase'], 'capture_membership_updated')
        self.assertIn('processed', move_res)
        self.assertIn('Backend Architecture', move_res['processed'])

    def test_watch_inbox_auto_processes_drops(self):
        folder = ensure_inbox_folder(self.author)
        stop_event = threading.Event()
        watch_thread = threading.Thread(
            target=watch_inbox,
            kwargs={'project': self.author, 'interval': 0.1, 'stop_event': stop_event}
        )
        watch_thread.daemon = True
        watch_thread.start()

        try:
            drop_file = folder / 'auto_note.txt'
            drop_file.write_text('Some dropped quick note for our knowledge base.', encoding='utf-8')
            # Wait for watcher to pick up and process
            for _ in range(30):
                if not drop_file.exists():
                    break
                time.sleep(0.1)

            self.assertFalse(drop_file.exists())
            scan = scan_inbox(self.author)
            self.assertEqual(scan['count'], 0)
        finally:
            stop_event.set()
            watch_thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
