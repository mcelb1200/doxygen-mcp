"""
Security tests for DoxygenConfig to prevent configuration injection.
"""

# pylint: disable=import-error
from doxygen_mcp.config import DoxygenConfig
# pylint: enable=import-error

class TestSecurityConfig:
    """Security tests for DoxygenConfig."""

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

        # It should appear as part of the value, quoted and escaped.
        # Original: src" -> src\"
        # \n -> space
        # INJECTED_KEY=VALUE -> INJECTED_KEY=VALUE
        # REM=" -> REM=\"
        # Wrapped in quotes: "src\" INJECTED_KEY=VALUE REM=\""
        expected_part = '"src\\" INJECTED_KEY=VALUE REM=\\""'
        assert expected_part in doxyfile_content

        # Normal path should also be quoted
        assert '"normal_path"' in doxyfile_content

    def test_list_paths_with_spaces(self):
        """Test that paths with spaces are correctly quoted."""
        path_with_spaces = "path/to/my project"
        config = DoxygenConfig(input_paths=[path_with_spaces])
        doxyfile_content = config.to_doxyfile()

        # Should be quoted: "path/to/my project"
        assert '"path/to/my project"' in doxyfile_content

    def test_list_paths_windows_style(self):
        """Test that Windows paths (backslashes) are correctly escaped and quoted."""
        win_path = r"C:\Users\Name\Project"
        config = DoxygenConfig(input_paths=[win_path])
        doxyfile_content = config.to_doxyfile()

        # Should be escaped: C:\\Users\\Name\\Project
        # And quoted: "C:\\Users\\Name\\Project"
        expected = '"C:\\\\Users\\\\Name\\\\Project"'
        assert expected in doxyfile_content

    def test_output_directory_traversal_injection(self):
        """Test that output directory is sanitized."""
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

    def test_control_character_injection(self):
        """Test that control characters (including line breaks) are sanitized."""
        # Inject vertical tab, form feed, etc.
        malicious_name = 'My Project\vINJECTED=YES\fREM='
        config = DoxygenConfig(project_name=malicious_name)
        doxyfile_content = config.to_doxyfile()

        # Should not contain unescaped control characters
        assert '\v' not in doxyfile_content
        assert '\f' not in doxyfile_content
        assert '\nINJECTED=YES' not in doxyfile_content
