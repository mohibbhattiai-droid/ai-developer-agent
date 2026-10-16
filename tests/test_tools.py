import tempfile
import unittest
from pathlib import Path

from ai_dev_agent.tools import WorkspaceTools


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.tools = WorkspaceTools(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_read_and_list(self):
        result = self.tools.execute("write_file", {"path": "src/hello.py", "content": "print('hello')\n"})
        self.assertTrue(result["ok"], result)
        read = self.tools.execute("read_file", {"path": "src/hello.py"})
        self.assertTrue(read["ok"], read)
        self.assertEqual(read["result"]["content"], "print('hello')\n")
        listing = self.tools.execute("list_files", {"path": "."})
        self.assertIn("src/hello.py", listing["result"]["files"])

    def test_refuses_overwrite_without_explicit_flag(self):
        self.tools.execute("write_file", {"path": "note.txt", "content": "original"})
        result = self.tools.execute("write_file", {"path": "note.txt", "content": "changed"})
        self.assertFalse(result["ok"])
        self.assertEqual((self.root / "note.txt").read_text(encoding="utf-8"), "original")

    def test_explicit_overwrite_works(self):
        self.tools.execute("write_file", {"path": "note.txt", "content": "original"})
        result = self.tools.execute("write_file", {"path": "note.txt", "content": "changed", "overwrite": True})
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.root / "note.txt").read_text(encoding="utf-8"), "changed")

    def test_path_traversal_and_absolute_paths_are_blocked(self):
        for path in ("../outside.txt", "/tmp/outside.txt", "C:\\Windows\\win.ini"):
            with self.subTest(path=path):
                result = self.tools.execute("read_file", {"path": path})
                self.assertFalse(result["ok"])

    def test_python_syntax_check_passes_and_fails(self):
        self.tools.execute("write_file", {"path": "good.py", "content": "def add(a, b):\n    return a + b\n"})
        good = self.tools.execute("check_python_syntax", {"path": "good.py"})
        self.assertTrue(good["ok"])
        self.assertTrue(good["result"]["valid"])

        self.tools.execute("write_file", {"path": "bad.py", "content": "def broken(:\n    pass\n"})
        bad = self.tools.execute("check_python_syntax", {"path": "bad.py"})
        self.assertTrue(bad["ok"])
        self.assertFalse(bad["result"]["valid"])
        self.assertEqual(bad["result"]["line"], 1)

    def test_search_files(self):
        self.tools.execute("write_file", {"path": "src/app.py", "content": "# TODO: add tests\nprint('ready')\n"})
        result = self.tools.execute("search_files", {"query": "todo"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["match_count"], 1)
        self.assertEqual(result["result"]["matches"][0]["line"], 1)

    def test_non_boolean_overwrite_is_rejected(self):
        self.tools.execute("write_file", {"path": "note.txt", "content": "original"})
        result = self.tools.execute("write_file", {"path": "note.txt", "content": "changed", "overwrite": "true"})
        self.assertFalse(result["ok"])
        self.assertEqual((self.root / "note.txt").read_text(encoding="utf-8"), "original")

    def test_likely_secret_files_are_blocked(self):
        (self.root / ".env").write_text("TOKEN=hidden", encoding="utf-8")
        read = self.tools.execute("read_file", {"path": ".env"})
        write = self.tools.execute("write_file", {"path": ".env", "content": "TOKEN=changed", "overwrite": True})
        listing = self.tools.execute("list_files", {"path": "."})
        self.assertFalse(read["ok"])
        self.assertFalse(write["ok"])
        self.assertNotIn(".env", listing["result"]["files"])

    def test_unknown_tool_is_handled(self):
        result = self.tools.execute("run_anything", {})
        self.assertFalse(result["ok"])
        self.assertIn("Unknown tool", result["error"])


if __name__ == "__main__":
    unittest.main()
