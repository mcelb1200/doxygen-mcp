
import pytest
from doxygen_mcp.config import DoxygenConfig

class TestSecurityConfig:
    """
    Security tests for DoxygenConfig to prevent configuration injection.
    """

    def test_project_name_injection(self):
        """Test preventing injection via project_name."""
        malicious_name = 'My Project"\nINPUT_FILTER = "echo HACKED > hacked.txt"\nREM="'
        config = DoxygenConfig(project_name=malicious_name)
        doxyfile_content = config.to_doxyfile()

        # Should not contain unescaped newlines or the injected key
        assert 'INPUT_FILTER = "echo HACKED > hacked.txt"' not in doxyfile_content
        # The newline should have been replaced by space
        assert 'My Project" INPUT_FILTER' in doxyfile_content.replace('\\"', '"')

    def test_input_paths_injection(self):
        """Test preventing injection via input_paths."""
        malicious_path = 'src"\nINJECTED_KEY=VALUE\nREM="'
        config = DoxygenConfig(input_paths=['normal_path', malicious_path])
        doxyfile_content = config.to_doxyfile()

        # The injected key should not appear at the start of a line
        assert '\nINJECTED_KEY=VALUE' not in doxyfile_content
        # It should appear as part of the value (space separated)
        # We need to handle the fact that sanitization replaces \n with space
        # and escapes quotes.
        # Original: src" -> src\"
        # \n -> space
        # INJECTED_KEY=VALUE -> INJECTED_KEY=VALUE
        # \n -> space
        # REM=" -> REM=\"
        expected_part = 'src\\" INJECTED_KEY=VALUE REM=\\"'
        assert expected_part in doxyfile_content

    def test_output_directory_traversal_injection(self):
        """Test that output directory is sanitized (though path traversal is handled elsewhere)."""
        malicious_dir = '../"\nINJECT=YES\n"'
        config = DoxygenConfig(output_directory=malicious_dir)
        doxyfile_content = config.to_doxyfile()

        # The injected key should not appear at the start of a line
        assert '\nINJECT=YES' not in doxyfile_content

        # Expected: "../\" INJECT=YES \"
        expected_part = '../\\" INJECT=YES \\"'
        assert expected_part in doxyfile_content

    def test_quote_escaping(self):
        """Test that quotes are properly escaped."""
        config = DoxygenConfig(project_name='Project with "quotes"')
        doxyfile_content = config.to_doxyfile()

        # Should be escaped as \"
        assert 'PROJECT_NAME           = "Project with \\"quotes\\""' in doxyfile_content

    def test_backslash_escaping(self):
        """Test that backslashes are properly escaped."""
        config = DoxygenConfig(project_name='Project with \\ backslash')
        doxyfile_content = config.to_doxyfile()

        # Should be escaped as \\
        assert 'PROJECT_NAME           = "Project with \\\\ backslash"' in doxyfile_content
