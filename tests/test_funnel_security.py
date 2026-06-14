import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# The environment might have defusedxml mocked in conftest.py,
# but for this standalone-ish test we want to be careful.
try:
    import defusedxml
except ImportError:
    # If not present (and not mocked yet), we can't really test XXE protection
    # unless we mock it ourselves to simulate the behavior.
    pass

from doxygen_mcp.funnel import minify_xml_file


class TestFunnel(unittest.TestCase):
    def test_minify_xml_file_removes_tags(self):
        with tempfile.NamedTemporaryFile(
            suffix=".xml", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class1" kind="class">
    <compoundname>Class1</compoundname>
    <collaborationgraph>Something</collaborationgraph>
    <briefdescription><para>Brief</para></briefdescription>
    <detaileddescription></detaileddescription>
  </compounddef>
</doxygen>
"""
            )
            temp_path = f.name

        try:
            success = minify_xml_file(temp_path)
            self.assertTrue(success)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("collaborationgraph", content)
                self.assertIn("briefdescription", content)
                self.assertNotIn(
                    "detaileddescription", content
                )  # It should be removed if empty
        finally:
            os.remove(temp_path)

    def test_minify_xml_safe_parsing(self):
        # Verify that defusedxml blocks XML files with XXE entities by returning False
        with tempfile.NamedTemporaryFile(
            suffix=".xml", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                """<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>
"""
            )
            temp_path = f.name

        try:
            success = minify_xml_file(temp_path)
            self.assertFalse(success)
        finally:
            os.remove(temp_path)

    def test_get_git_hooks_dir_fallback(self):
        from doxygen_mcp.funnel import get_git_hooks_dir

        repo = Path("/mock/repo")
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("error")
            hooks_dir = get_git_hooks_dir(repo)
            self.assertEqual(hooks_dir, repo / ".git" / "hooks")

    def test_get_git_hooks_dir_worktree(self):
        from doxygen_mcp.funnel import get_git_hooks_dir

        repo = Path("/mock/repo")
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "/main/repo/.git/worktrees/wt1/hooks\n"
            mock_run.return_value = mock_result

            hooks_dir = get_git_hooks_dir(repo)
            self.assertEqual(hooks_dir, Path("/main/repo/.git/worktrees/wt1/hooks"))


if __name__ == "__main__":
    unittest.main()
