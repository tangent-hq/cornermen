"""rename.py: renames a copy of the repo end to end, then the install tests still pass in the copy."""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class RenameTest(unittest.TestCase):
    def setUp(self):
        self.copy = Path(tempfile.mkdtemp()) / "repo"
        shutil.copytree(REPO, self.copy, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.png"))
        src = (self.copy / "scripts" / "rename.py").read_text()
        self.old = re.search(r'^CURRENT_SLUG = "([^"]+)"', src, re.M).group(1)

    def run_rename(self, *args):
        return subprocess.run([sys.executable, str(self.copy / "scripts" / "rename.py"), *args],
                              cwd=self.copy, capture_output=True, text=True)

    def grep(self, needle):
        return [p for p in self.copy.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and needle in p.read_text(errors="ignore")]

    def test_dry_run_writes_nothing(self):
        res = self.run_rename("Sample Name", "--dry-run")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("dry run", res.stdout)
        self.assertTrue((self.copy / "skills" / self.old).is_dir())
        self.assertTrue(self.grep(self.old))

    def test_rename_then_install_tests_pass(self):
        res = self.run_rename("Sample Name")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self.grep(self.old), [])
        self.assertTrue((self.copy / "skills" / "sample-name" / "SKILL.md").is_file())
        self.assertTrue((self.copy / "README.md").read_text().startswith("# Sample Name\n"))
        self.assertIn("Sample Name contributors", (self.copy / "LICENSE").read_text())
        self.assertIn("name: sample-name", (self.copy / "skills" / "sample-name" / "SKILL.md").read_text())
        # Second run is refused cleanly (already renamed).
        self.assertEqual(self.run_rename("Sample Name").returncode, 0)  # slug unchanged -> no-op
        tests = subprocess.run([sys.executable, "-m", "unittest", "tests.test_install", "-q"],
                               cwd=self.copy, capture_output=True, text=True)
        self.assertEqual(tests.returncode, 0, tests.stderr[-2000:])

    def test_bad_slug_rejected(self):
        self.assertEqual(self.run_rename("X", "--slug", "Bad Slug!").returncode, 2)


if __name__ == "__main__":
    unittest.main()
