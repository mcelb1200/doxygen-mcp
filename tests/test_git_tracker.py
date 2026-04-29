"""
Tests for Git Tracker Utility
"""
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from doxygen_mcp.git_tracker import (
    get_git_root,
    check_working_tree,
    check_branch_state,
    get_file_timeline
)

def test_get_git_root_success():
    """Test successful git root retrieval."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "/path/to/repo\n"
        mock_run.return_value = mock_result

        root = get_git_root(Path("/path/to/repo/file.py"))
        assert root == Path("/path/to/repo")
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "rev-parse", "--show-toplevel"]

def test_get_git_root_failure():
    """Test git root retrieval failure."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

        root = get_git_root(Path("/path/to/repo/file.py"))
        assert root is None

def test_check_working_tree_clean():
    """Test clean working tree."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        status = check_working_tree(repo_root, filepath)
        assert status == "[CLEAN]"

def test_check_working_tree_untracked():
    """Test untracked file in working tree."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "?? file.py\n"
        mock_run.return_value = mock_result

        status = check_working_tree(repo_root, filepath)
        assert "[UNTRACKED]" in status

def test_check_working_tree_modified():
    """Test modified file in working tree."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = " M file.py\n"
        mock_run.return_value = mock_result

        status = check_working_tree(repo_root, filepath)
        assert "[UNCOMMITTED CHANGES]" in status

def test_check_working_tree_error():
    """Test error during working tree check."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Subprocess error")

        status = check_working_tree(repo_root, filepath)
        assert status == "[UNKNOWN]"

def test_check_branch_state_synced():
    """Test synced branch state."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        # Mock merge-base call
        mock_base = MagicMock()
        mock_base.stdout = "abcdef\n"
        # Mock diff call
        mock_diff = MagicMock()
        mock_diff.stdout = ""

        mock_run.side_effect = [mock_base, mock_diff]

        status = check_branch_state(repo_root, filepath)
        assert status == "[SYNCED]"
        assert mock_run.call_count == 2

def test_check_branch_state_modified():
    """Test modified branch state."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        # Mock merge-base call
        mock_base = MagicMock()
        mock_base.stdout = "abcdef\n"
        # Mock diff call
        mock_diff = MagicMock()
        mock_diff.stdout = "M\tfile.py\n"

        mock_run.side_effect = [mock_base, mock_diff]

        status = check_branch_state(repo_root, filepath)
        assert "[MODIFIED FROM MAIN]" in status

def test_check_branch_state_fallback_master():
    """Test fallback to master branch."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        # Mock main fail
        # merge-base main fails
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, ["git", "merge-base"]),
            MagicMock(stdout="abcdef\n"), # merge-base master succeeds
            MagicMock(stdout="M\tfile.py\n") # diff master succeeds
        ]

        status = check_branch_state(repo_root, filepath)
        assert "[MODIFIED FROM MAIN]" in status
        assert mock_run.call_count == 3

def test_check_branch_state_unknown():
    """Test unknown base branch."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "merge-base"])

        status = check_branch_state(repo_root, filepath)
        assert status == "[UNKNOWN BASE BRANCH]"

def test_check_branch_state_exception():
    """Test exception in branch state check."""
    repo_root = Path("/path/to/repo")
    filepath = Path("/path/to/repo/file.py")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Unexpected error")

        status = check_branch_state(repo_root, filepath)
        assert status == "[UNKNOWN]"

@patch("doxygen_mcp.git_tracker.get_git_root")
@patch("doxygen_mcp.git_tracker.check_working_tree")
@patch("doxygen_mcp.git_tracker.check_branch_state")
@patch("pathlib.Path.resolve")
def test_get_file_timeline_success(mock_resolve, mock_branch, mock_tree, mock_root):
    """Test successful timeline generation."""
    mock_resolve.return_value = Path("/path/to/repo/file.py")
    mock_root.return_value = Path("/path/to/repo")
    mock_tree.return_value = "[CLEAN]"
    mock_branch.return_value = "[SYNCED]"

    timeline = get_file_timeline("/path/to/repo/file.py")

    assert "[SYMBOL TIMELINE: file.py]" in timeline
    assert "Documentation State: Reflects HEAD commit ('What Was')." in timeline
    assert "Working Tree State: [CLEAN]" in timeline
    assert "Branch State: [SYNCED]" in timeline

@patch("doxygen_mcp.git_tracker.get_git_root")
@patch("pathlib.Path.resolve")
def test_get_file_timeline_no_git(mock_resolve, mock_root):
    """Test timeline generation outside git repo."""
    mock_resolve.return_value = Path("/non/git/file.py")
    mock_root.return_value = None

    timeline = get_file_timeline("/non/git/file.py")
    assert "[STATUS: ERROR]" in timeline
    assert "is not in a git repository" in timeline

@patch("doxygen_mcp.git_tracker.get_git_root")
@patch("doxygen_mcp.git_tracker.check_working_tree")
@patch("doxygen_mcp.git_tracker.check_branch_state")
@patch("pathlib.Path.resolve")
def test_get_file_timeline_not_indexed(mock_resolve, mock_branch, mock_tree, mock_root):
    """Test timeline generation for non-indexed file."""
    mock_resolve.return_value = Path("/path/to/repo/file.py")
    mock_root.return_value = Path("/path/to/repo")
    mock_tree.return_value = "[CLEAN]"
    mock_branch.return_value = "[SYNCED]"

    timeline = get_file_timeline("/path/to/repo/file.py", is_indexed=False)

    assert "Documentation State: [NOT INDEXED]" in timeline
