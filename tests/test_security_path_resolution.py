"""
Security tests for resolve_project_path utility.
"""
# pylint: disable=import-error, wrong-import-position
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from doxygen_mcp.utils import resolve_project_path

def test_path_traversal_denied():
    """Test that path traversal outside safe roots is denied."""
    with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": "/app/project", "PYTEST_CURRENT_TEST": ""}):
        with pytest.raises(ValueError) as excinfo:
            resolve_project_path("/etc/passwd")
        assert "Security Error" in str(excinfo.value)
