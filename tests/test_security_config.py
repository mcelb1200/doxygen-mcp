"""
# pylint: disable=import-error, redefined-outer-name
Security tests for DoxygenConfig to prevent configuration injection.
"""
# pylint: disable=import-error, redefined-outer-name
# pylint: disable=import-error
import pytest
from doxygen_mcp.config import DoxygenConfig

class TestSecurityConfig:
    """Security tests for DoxygenConfig."""
# pylint: disable=import-error, redefined-outer-name

    def test_project_name_injection(self):
        """Test preventing injection via project_name."""
# pylint: disable=import-error, redefined-outer-name
        malicious_name = 'My Project"\nINPUT_FILTER = "echo HACKED > hacked.txt"\nREM="'
        config = DoxygenConfig(project_name=malicious_name)
        doxyfile_content = config.to_doxyfile()

        # Should not contain unescaped newlines or the injected key
        assert 'INPUT_FILTER = "echo HACKED > hacked.txt"' not in doxyfile_content
        # The newline should have been replaced by space
        assert 'My Project" INPUT_FILTER' in doxyfile_content.replace('\\"', '"')
