
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import from src
sys.path.insert(0, os.path.abspath("src"))

from doxygen_mcp.utils import resolve_project_path

# Mock for tempfile.gettempdir if needed, but we can rely on os.environ
import tempfile

class TestSecurityPathResolution:

    @pytest.fixture(autouse=True)
    def clean_env(self):
        """Clean environment variables before each test"""
        vars_to_clear = [
            "DOXYGEN_PROJECT_ROOT",
            "VSCODE_WORKSPACE_FOLDER",
            "CURSOR_WORKSPACE_PATH",
            "GEMINI_PROJECT_ROOT",
            "ACTIVE_WORKSPACE_PATH",
            "DOXYGEN_ALLOWED_PATHS",
            # We don't clear PYTEST_CURRENT_TEST here because pytest might re-add it
            # We will handle it explicitly in tests where needed.
        ]
        old_env = {}
        for var in vars_to_clear:
            if var in os.environ:
                old_env[var] = os.environ[var]
                del os.environ[var]

        # Ensure PWD is set to CWD
        old_pwd = os.environ.get("PWD")
        os.environ["PWD"] = os.getcwd()

        yield

        # Restore
        for var, val in old_env.items():
            os.environ[var] = val
        if old_pwd:
            os.environ["PWD"] = old_pwd
        else:
            if "PWD" in os.environ: del os.environ["PWD"]

    def _ensure_strict_mode(self):
        """Helper to ensure PYTEST_CURRENT_TEST is unset for strict security testing"""
        if "PYTEST_CURRENT_TEST" in os.environ:
            del os.environ["PYTEST_CURRENT_TEST"]

    def test_allow_cwd_subpath(self, tmp_path):
        """Test allowing paths within the discovered root (CWD)"""
        # Set CWD to tmp_path
        with patch("doxygen_mcp.utils.Path.cwd", return_value=tmp_path):
            with patch.dict(os.environ, {"PWD": str(tmp_path)}):
                # Valid subpath
                subpath = tmp_path / "subdir"
                subpath.mkdir()

                resolved = resolve_project_path(str(subpath))
                assert resolved == subpath.resolve()

    def test_block_parent_traversal(self, tmp_path):
        """Test blocking paths outside the discovered root using .."""
        cwd = tmp_path / "project"
        cwd.mkdir()

        outside = tmp_path / "secret.txt"
        outside.touch()

        with patch("doxygen_mcp.utils.Path.cwd", return_value=cwd):
            with patch.dict(os.environ, {"PWD": str(cwd)}):
                # IMPORTANT: Remove PYTEST_CURRENT_TEST to prevent bypass for paths in /tmp
                self._ensure_strict_mode()

                # Try to access ../secret.txt
                malicious_path = str(cwd / "../secret.txt")

                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(malicious_path)

    def test_block_absolute_path_outside(self, tmp_path):
        """Test blocking absolute paths outside the root"""
        cwd = tmp_path / "project"
        cwd.mkdir()

        outside = tmp_path / "other"
        outside.mkdir()

        with patch("doxygen_mcp.utils.Path.cwd", return_value=cwd):
             with patch.dict(os.environ, {"PWD": str(cwd)}):
                self._ensure_strict_mode()

                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(str(outside))

    def test_allow_explicit_env_root(self, tmp_path):
        """Test that DOXYGEN_PROJECT_ROOT allows access to its children"""
        root = tmp_path / "custom_root"
        root.mkdir()

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": str(root)}):
            child = root / "child"
            child.mkdir()
            resolved = resolve_project_path(str(child))
            assert resolved == child.resolve()

    def test_symlink_traversal_prevention(self, tmp_path):
        """Test that symlinks pointing outside are blocked"""
        cwd = tmp_path / "project"
        cwd.mkdir()

        outside = tmp_path / "target"
        outside.mkdir()

        # Create symlink inside cwd pointing to outside
        link = cwd / "mylink"
        try:
            os.symlink(outside, link)
        except OSError:
            pytest.skip("Symlinks not supported")

        with patch("doxygen_mcp.utils.Path.cwd", return_value=cwd):
             with patch.dict(os.environ, {"PWD": str(cwd)}):
                self._ensure_strict_mode()

                # Resolving the link should resolve to 'outside', which is not in 'cwd'
                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(str(link))

    def test_pytest_bypass_behavior(self, tmp_path):
        """
        Verify the pytest bypass behavior.
        We expect paths starting with /tmp or /var/tmp to be allowed IF PYTEST_CURRENT_TEST is set.
        """
        cwd = tmp_path / "project"
        cwd.mkdir()

        # A path in /tmp (simulated)
        real_temp = Path(tempfile.gettempdir())
        target = real_temp / "doxygen_mcp_test_file"
        target.touch()

        with patch("doxygen_mcp.utils.Path.cwd", return_value=cwd):
            with patch.dict(os.environ, {"PWD": str(cwd), "PYTEST_CURRENT_TEST": "1"}):
                # Should be allowed because it is in tempdir and PYTEST_CURRENT_TEST is set
                # (Assuming tempdir starts with /tmp or /var/tmp)
                try:
                    resolve_project_path(str(target))
                except ValueError:
                    if not (str(target).startswith("/tmp") or str(target).startswith("/var/tmp")):
                        print(f"Skipping test_pytest_bypass_behavior check for real temp dir {target} as it's not standard.")
                    else:
                        raise

        target.unlink(missing_ok=True)

    def test_pytest_bypass_abuse_prevention(self, tmp_path):
        """
        Verify that having 'temp' in the name is NOT enough anymore.
        The previous vulnerable code allowed any path with 'temp' in it.
        We want to ensure we block paths like .../templates/secret even if PYTEST_CURRENT_TEST is set.
        """
        cwd = tmp_path / "project"
        cwd.mkdir()

        # We simulate a path that is NOT /tmp.
        fake_path = "/home/user/templates/secret"

        with patch("doxygen_mcp.utils.Path.cwd", return_value=cwd):
            with patch.dict(os.environ, {"PWD": str(cwd), "PYTEST_CURRENT_TEST": "1"}):
                # We don't patch os.path.abspath, we rely on it resolving normally.
                # Since fake_path is absolute, abspath returns it.
                # realpath returns it (if no symlinks).

                # This SHOULD fail with the strict fix.
                # It would PASS with the loose 'temp' in path check.
                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(fake_path)

    def test_pytest_bypass_prefix_traversal_prevention(self, tmp_path):
        """
        Verify that path starting with /tmp but not in /tmp (e.g. /tmp_evil) is blocked.
        """
        cwd = tmp_path / "project"
        cwd.mkdir()

        fake_path = "/tmp_evil/secret"

        with patch("doxygen_mcp.utils.Path.cwd", return_value=cwd):
            with patch.dict(os.environ, {"PWD": str(cwd), "PYTEST_CURRENT_TEST": "1"}):
                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(fake_path)
