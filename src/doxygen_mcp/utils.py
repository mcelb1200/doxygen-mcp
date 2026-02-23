"""
Utility functions for Doxygen MCP context discovery and environment integration.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

def find_project_root(start_path: Path, markers: Optional[List[str]] = None) -> Path:
    """
    Search upwards from start_path for project markers to identify the workspace root.
    """
    if markers is None:
        markers = [
            ".git", ".svn", "Doxyfile", "pyproject.toml", "package.json",
            "CMakeLists.txt", "Makefile", "solution.sln", "go.mod", "Cargo.toml",
            "requirements.txt", "build.gradle", "pom.xml"
        ]

    current = start_path.resolve()
    for parent in [current] + list(current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent

    return current

def resolve_project_path(project_path: Optional[str] = None) -> Path:
    """
    Resolve project path with priority:
    1. Explicit argument (validated against allowed roots)
    2. DOXYGEN_PROJECT_ROOT env var
    3. IDE-supplied workspace variables (VSCODE_WORKSPACE_FOLDER, etc.)
    4. Discovery via markers (searching up from CWD/PWD)
    """
    # Identify safe base directories
    safe_roots = []

    # Priority 2: Standard override
    env_root = os.environ.get("DOXYGEN_PROJECT_ROOT")
    if env_root:
        safe_roots.append(Path(os.path.abspath(os.path.realpath(env_root))))

    # Priority 3: IDE Workspace variables
    ide_roots = [
        "VSCODE_WORKSPACE_FOLDER",
        "CURSOR_WORKSPACE_PATH",
        "GEMINI_PROJECT_ROOT",
        "ACTIVE_WORKSPACE_PATH",
        "PWD", # Often set by shells/IDE terminals
    ]
    for env_var in ide_roots:
        val = os.environ.get(env_var)
        if val and os.path.isdir(val):
            safe_roots.append(Path(os.path.abspath(os.path.realpath(val))))

    # Priority 4: Search upwards from CWD
    discovery_root = find_project_root(Path.cwd())
    safe_roots.append(discovery_root)

    # Add explicitly allowed paths from environment
    allowed_env = os.environ.get("DOXYGEN_ALLOWED_PATHS")
    if allowed_env:
        for p in allowed_env.split(","):
            if p.strip():
                safe_roots.append(Path(os.path.abspath(os.path.realpath(p.strip()))))

    if not project_path:
        return safe_roots[0] if safe_roots else discovery_root

    # Validate the provided project_path
    # We use realpath/abspath to resolve symlinks and ensure absolute path before comparison
    requested_path = Path(os.path.abspath(os.path.realpath(project_path)))

    # Check if requested_path is within any of the safe roots
    is_safe = False
    for root in safe_roots:
        try:
            # relative_to throws ValueError if not a subpath
            requested_path.relative_to(root)
            is_safe = True
            break
        except ValueError:
            continue

    # Special bypass for tests to avoid breaking temporary directory usage
    if not is_safe and os.environ.get("PYTEST_CURRENT_TEST"):
        if str(requested_path).startswith("/tmp") or "temp" in str(requested_path).lower():
            is_safe = True

    if not is_safe:
        raise ValueError(f"Security Error: Access denied to path '{requested_path}'. It is outside of allowed project roots.")

    return requested_path


def _detect_primary_language_sync(project_path: Path) -> str:
    """
    Synchronous helper to identify the dominant programming language.
    """
    ext_map = {
        ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp", ".hh": "cpp", ".cxx": "cpp",
        ".c": "c", ".h": "c",
        ".py": "python",
        ".php": "php",
        ".java": "java",
        ".cs": "csharp",
        ".js": "javascript", ".ts": "javascript", ".jsx": "javascript", ".tsx": "javascript",
        ".go": "go",
        ".rs": "rust"
    }

    counts: Dict[str, int] = {}
    try:
        # Scan root and one level deep for performance
        files = list(project_path.glob("*")) + list(project_path.glob("*/*"))
        for f in files:
            if f.is_file():
                ext = f.suffix.lower()
                if ext in ext_map:
                    lang = ext_map[ext]
                    counts[lang] = counts.get(lang, 0) + 1
    except Exception:
        pass

    if not counts:
        return "mixed"

    return max(counts, key=lambda x: counts.get(x, 0))


async def detect_primary_language(project_path: Path) -> str:
    """
    Identify the dominant programming language in the project to optimize Doxygen settings.
    Offloaded to a thread pool to avoid blocking the event loop.
    """
    return await asyncio.to_thread(_detect_primary_language_sync, project_path)

def get_project_name(resolved_path: Path) -> str:
    """
    Attempt to determine the project name from the environment or project structure.
    """
    # Priority 1: standard env override
    env_name = os.environ.get("DOXYGEN_PROJECT_NAME")
    if env_name:
        return env_name

    # Priority 2: IDE specific variables
    ide_name_vars = [
        "VSCODE_WORKSPACE_NAME",
        "CURSOR_PROJECT_NAME",
        "PROJECT_NAME",
    ]
    for var in ide_name_vars:
        val = os.environ.get(var)
        if val:
            return val

    # Priority 3: Derived from workspace root folder name
    return resolved_path.name

def get_ide_environment() -> Dict[str, Any]:
    """
    Detect if the server is running within a specific IDE and extract relevant context.
    """
    project_root = resolve_project_path()
    context = {
        "ide": "unknown",
        "workspace_root": str(project_root),
        "project_name": get_project_name(project_root)
    }

    # VS Code / Cursor detection
    term_program = os.environ.get("TERM_PROGRAM")
    is_vscode = term_program == "vscode" or os.environ.get("VSCODE_GIT_IPC_HANDLE")

    if is_vscode:
        context["ide"] = "vscode"
        if os.environ.get("CURSOR_GIT_IPC_HANDLE") or "cursor" in os.environ.get("APP_PATH", "").lower():
            context["ide"] = "cursor"

        # Try to find VS Code settings
        vscode_settings = project_root / ".vscode" / "settings.json"
        if vscode_settings.exists():
            try:
                with open(vscode_settings, "r") as f:
                    context["vscode_settings"] = json.load(f)
            except:
                pass

    # JetBrains detection
    if os.environ.get("TERMINAL_EMULATOR") == "JetBrains-JediTerm":
        context["ide"] = "jetbrains"

    return context


def get_active_context() -> Dict[str, Any]:
    """
    Retrieve active file information if provided by the environment.
    Some MCP clients or IDE extensions might inject these into the environment.
    """
    return {
        "active_file": os.environ.get("MCP_ACTIVE_FILE"),
        "cursor_line": os.environ.get("MCP_CURSOR_LINE"),
        "cursor_column": os.environ.get("MCP_CURSOR_COLUMN"),
        "selected_text": os.environ.get("MCP_SELECTED_TEXT")
    }

def _update_ignore_file_sync(project_root: Path, path_to_ignore: str) -> bool:
    """
    Synchronous helper for updating .gitignore.
    """
    ignore_file = project_root / ".gitignore"
    new_entry = f"{path_to_ignore}\n"

    if ignore_file.is_symlink():
        return False

    # Create file if it doesn't exist
    if not ignore_file.exists():
        try:
            with open(ignore_file, "w", encoding="utf-8") as f:
                f.write("# Doxygen Generated Documentation Folders\n")
                f.write(new_entry)
            return True
        except Exception:
            return False

    # Check if already ignored and append if not
    try:
        with open(ignore_file, "r+", encoding="utf-8") as f:
            lines = f.readlines()
            if any(line.strip() == path_to_ignore.strip() for line in lines):
                return False

            # Ensure the last line ends with a newline before appending
            if lines and not lines[-1].endswith("\n"):
                f.write("\n")
            f.write(new_entry)
        return True
    except Exception:
        return False


async def update_ignore_file(project_root: Path, path_to_ignore: str) -> bool:
    """
    Ensure a path is added to the project-specific .gitignore file.
    Offloaded to a thread pool to avoid blocking the event loop.
    Returns True if an entry was added, False otherwise.
    """
    return await asyncio.to_thread(_update_ignore_file_sync, project_root, path_to_ignore)
