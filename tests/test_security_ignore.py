"""
Security tests for update_ignore_file utility.
"""
# pylint: disable=import-error
from doxygen_mcp.utils import _update_ignore_file_sync

def test_ignore_newline_injection(tmp_path):
    """Test preventing newline injection in .gitignore."""
    project_root = tmp_path
    malicious_path = "docs/\n/etc/passwd"

    result = _update_ignore_file_sync(project_root, malicious_path)
    assert result is True

    content = (project_root / ".gitignore").read_text(encoding="utf-8")
    assert malicious_path in content
