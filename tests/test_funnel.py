import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doxygen_mcp.funnel import filter_main, setup_funnel, setup_main


def test_setup_funnel_success(tmp_path):
    repo = tmp_path / "my_repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    # Stub git rev-parse to succeed and return correct values
    with patch("subprocess.run") as mock_run:

        def mock_run_side_effect(args, **kwargs):
            mock_res = MagicMock(returncode=0)
            if "--git-dir" in args:
                mock_res.stdout = ".git\n"
            elif "--git-path" in args and "hooks" in args:
                mock_res.stdout = ".git/hooks\n"
            else:
                mock_res.stdout = "\n"
            return mock_res

        mock_run.side_effect = mock_run_side_effect

        success, msg = setup_funnel(str(repo))
        assert success is True
        assert "Successfully configured" in msg
        assert (repo / "Doxyfile.fast").exists()
        assert (repo / ".git" / "hooks" / "post-commit").exists()


def test_setup_funnel_not_git(tmp_path):
    repo = tmp_path / "not_a_repo"
    repo.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("failed")
        success, msg = setup_funnel(str(repo))
        assert success is False
        assert "Not a git repository" in msg


def test_filter_main(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()

    # Write some dummy XML files
    f1 = xml_dir / "file1.xml"
    f1.write_text("<root></root>", encoding="utf-8")

    with (
        patch("sys.argv", ["doxygen-snr-filter", str(xml_dir)]),
        patch("sys.exit") as mock_exit,
    ):
        filter_main()
        # Should not exit on success, or call print
        mock_exit.assert_not_called()


def test_setup_main(tmp_path):
    repo = tmp_path / "my_repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    with (
        patch("sys.argv", ["doxygen-setup-funnel", str(repo)]),
        patch("sys.exit") as mock_exit,
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")
        setup_main()
        mock_exit.assert_called_once_with(0)
