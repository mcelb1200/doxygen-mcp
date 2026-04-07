#!/usr/bin/env python3
"""
Doxygen MCP Server - Context Aware Version
"""

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
try:
    from importlib.metadata import version as get_package_version
except ImportError:
    # Fallback for Python < 3.8
    try:
        from importlib_metadata import version as get_package_version # type: ignore
    except ImportError:
        get_package_version = None # type: ignore

# MCP server imports
from mcp.server.fastmcp import FastMCP
from .query_engine import DoxygenQueryEngine
from .config import DoxygenConfig
from .utils import (
    resolve_project_path,
    detect_primary_language,
    get_ide_environment,
    update_ignore_file,
    get_active_context,
    get_doxygen_executable
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doxygen-mcp")

mcp = FastMCP("Doxygen")

# Cache for Doxygen version check
_DOXYGEN_VERSION_CACHE: Dict[str, str] = {}

# Common directories to skip for performance during filesystem scans
SCAN_SKIP_DIRS = {
    'node_modules', 'build', 'dist', 'target', 'venv', 'env', '__pycache__',
    'bower_components', 'extern', 'external', 'vendor'
}

def _find_xml_dir(resolved_path: Path) -> Optional[str]:
    """
    Find the Doxygen XML directory with preference for:
    1. DOXYGEN_XML_DIR env var (absolute or relative)
    2. Standard locations within project root
    """
    xml_dir_env = os.environ.get("DOXYGEN_XML_DIR")
    if xml_dir_env:
        path = Path(xml_dir_env)
        if not path.is_absolute():
            path = resolved_path / path

        if path.exists() and (path / "index.xml").exists():
            return str(path.absolute())

    # Discovery in standard locations
    potential_paths = [
        resolved_path / "docs" / "xml",
        resolved_path / "xml",
        resolved_path / "doxygen" / "xml",
    ]
    for p in potential_paths:
        if p.exists() and (p / "index.xml").exists():
            return str(p.absolute())

    return None

async def _get_project_path(project_path: Optional[str] = None) -> Path:
    """Helper to resolve project path in a thread pool."""
    # pylint: disable=no-member
    return await asyncio.to_thread(resolve_project_path, project_path)

@mcp.tool()
async def get_context_info() -> Dict[str, Any]:
    """
    Get information about the current project context, detected language, and IDE environment.
    """
    try:
        # pylint: disable=no-member
        project_path = await asyncio.to_thread(resolve_project_path)
        language = await asyncio.to_thread(detect_primary_language, project_path)
        ide_info = await asyncio.to_thread(get_ide_environment)
        active_context = get_active_context()

        has_doxyfile = await asyncio.to_thread((project_path / "Doxyfile").exists)

        return {
            "project_root": str(project_path),
            "detected_language": language,
            "ide_environment": ide_info,
            "active_context": active_context,
            "doxygen_status": {
                "has_doxyfile": has_doxyfile,
                "config_path": str(project_path / "Doxyfile") if has_doxyfile else None
            }
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": str(e)}

@mcp.tool()
async def auto_configure(project_name: Optional[str] = None) -> str:
    """
    Automatically detect project settings and create a Doxyfile if one doesn't exist.
    """
    try:
        # pylint: disable=no-member
        project_path = await asyncio.to_thread(resolve_project_path)
        if not project_name:
            project_name = project_path.name

        language = await asyncio.to_thread(detect_primary_language, project_path)

        doxyfile_exists = await asyncio.to_thread((project_path / "Doxyfile").exists)
        if doxyfile_exists:
            return f"✨ Project already configured at {project_path}. Detected language: {language}."

        result = await create_doxygen_project(
            project_name=project_name,
            project_path=str(project_path),
            language=language
        )

        return f"🚀 Auto-configured project!\n\n{result}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Auto-configuration failed: {str(e)}"

def _write_doxyfile_sync(path: Path, content: str) -> None:
    """Helper to write Doxyfile synchronously."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

@mcp.tool()
async def create_doxygen_project(
    project_name: str,
    project_path: Optional[str] = None,
    language: Optional[str] = None,
    include_subdirs: bool = True,
    extract_private: bool = False,
    follow_symlinks: bool = False,
) -> str:
    """Initialize a new Doxygen documentation project with configuration"""
    try:
        # Resolve project path and detect language if not provided
        # pylint: disable=no-member
        safe_project_path = await asyncio.to_thread(resolve_project_path, project_path)
        if language is None:
            language = await asyncio.to_thread(detect_primary_language, safe_project_path)

        path_exists = await asyncio.to_thread(safe_project_path.exists)
        path_is_dir = await asyncio.to_thread(safe_project_path.is_dir)
        if path_exists and not path_is_dir:
            return f"❌ Path exists but is not a directory: {safe_project_path}"

        # Create project directory if it doesn't exist
        await asyncio.to_thread(safe_project_path.mkdir, parents=True, exist_ok=True)

        # Create configuration based on language
        config = DoxygenConfig(
            project_name=project_name,
            output_directory=str(safe_project_path / "docs"),
            input_paths=[str(safe_project_path)],
            recursive=include_subdirs,
            extract_private=extract_private,
            exclude_symlinks=not follow_symlinks
        )

        # Language-specific optimizations
        lang_settings: Dict[str, Dict[str, Any]] = {
            "c": {"optimize_output_for_c": True, "file_patterns": ["*.c", "*.h"]},
            "cpp": {"file_patterns": ["*.cpp", "*.hpp", "*.cc", "*.hh", "*.cxx", "*.hxx"]},
            "python": {"optimize_output_java": True, "file_patterns": ["*.py"]},
            "php": {"file_patterns": ["*.php", "*.php3", "*.inc"]},
            "java": {"optimize_output_java": True, "file_patterns": ["*.java"]},
            "csharp": {"file_patterns": ["*.cs"]},
            "javascript": {"file_patterns": ["*.js", "*.jsx", "*.ts", "*.tsx"]},
        }

        if language in lang_settings:
            for key, value in lang_settings[language].items():
                setattr(config, key, value)

        # Save configuration
        doxyfile_path = safe_project_path / "Doxyfile"

        doxyfile_is_symlink = await asyncio.to_thread(doxyfile_path.is_symlink)
        if doxyfile_is_symlink:
            return f"❌ Security Error: {doxyfile_path} is a symlink. Cannot overwrite."
        doxyfile_exists = await asyncio.to_thread(doxyfile_path.exists)
        if doxyfile_exists:
            return (
                f"❌ Doxyfile already exists at {doxyfile_path}. "
                "Use 'auto_configure' or backup first."
            )

        # pylint: disable=no-member
        await asyncio.to_thread(_write_doxyfile_sync, doxyfile_path, config.to_doxyfile())

        # Update .gitignore
        await update_ignore_file(safe_project_path, "docs/")

        return (
            f"✅ Doxygen project '{project_name}' created successfully "
            f"at {safe_project_path} (Language: {language})"
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Failed to create project: {str(e)}"

@mcp.tool()
async def generate_documentation(
    project_path: Optional[str] = None,
    output_format: str = "html",  # pylint: disable=unused-argument
    verbose: bool = False,  # pylint: disable=unused-argument
) -> str:
    """Generate documentation from source code using Doxygen"""
    try:
        safe_project_path = await _get_project_path(project_path)
    except ValueError as e:
        return f"❌ {str(e)}"

    doxyfile_path = safe_project_path / "Doxyfile"
    if not doxyfile_path.exists():
        return "❌ No Doxyfile found. Run 'auto_configure' or 'create_doxygen_project' first."

    doxygen_exe = get_doxygen_executable()

    try:
        # Run Doxygen asynchronously with timeout
        process = await asyncio.create_subprocess_exec(
            doxygen_exe,
            str(doxyfile_path),
            cwd=str(safe_project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            # Set a 300-second timeout to prevent indefinite hangs
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass  # Process already finished
            await process.wait()
            return "❌ Documentation generation timed out after 300 seconds."

        stdout_text = stdout.decode(errors='replace') if stdout else ""
        stderr_text = stderr.decode(errors='replace') if stderr else ""

        if process.returncode == 0:
            # Clear all caches as documentation has been regenerated
            DoxygenQueryEngine.clear_cache()
            return (
                "✅ Documentation generated successfully at "
                f"{safe_project_path / 'docs' / 'html' / 'index.html'}"
            )

        return f"❌ Documentation generation failed:\n{stderr_text or stdout_text}"

    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error generating documentation: {str(e)}"

def _perform_scan(safe_project_path: Path):
    """Sync helper to scan the filesystem without blocking the event loop"""
    extensions: Dict[str, int] = {}
    total_files = 0

    for _, dirs, files in os.walk(safe_project_path):
        # Skip hidden directories and common large/irrelevant folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SCAN_SKIP_DIRS]

        for file in files:
            if file.startswith('.'):
                continue

            _, ext = os.path.splitext(file)
            if ext:
                ext_lower = ext.lower()
                extensions[ext_lower] = extensions.get(ext_lower, 0) + 1
                total_files += 1
    return extensions, total_files

@mcp.tool()
async def scan_project(
    project_path: Optional[str] = None,
) -> str:
    """Analyze project structure and identify documentation opportunities"""
    try:
        safe_project_path = await _get_project_path(project_path)
    except ValueError as e:
        return f"❌ {str(e)}"

    if not safe_project_path.exists():
        return f"❌ Project path does not exist: {safe_project_path}"

    # pylint: disable=no-member
    extensions, total_files = await asyncio.to_thread(_perform_scan, safe_project_path)

    sorted_extensions = sorted(extensions.items(), key=lambda x: x[1], reverse=True)
    result_text = (
        f"📁 Project Scan Results: {safe_project_path}\n"
        f"📊 Total Files Found: {total_files}\n\n📋 Files by Type:\n"
    )
    for ext, count in sorted_extensions[:10]:
        result_text += f"  📄 {ext}: {count} files\n"

    return result_text

@mcp.tool()
async def check_doxygen_install() -> str:
    """Verify that Doxygen is installed and accessible"""
    try:
        doxygen_exe = get_doxygen_executable()
        if doxygen_exe in _DOXYGEN_VERSION_CACHE:
            return _DOXYGEN_VERSION_CACHE[doxygen_exe]

        process = await asyncio.create_subprocess_exec(
            doxygen_exe,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            return "❌ Doxygen check timed out"

        if process.returncode != 0:
            return "❌ Doxygen is not installed or returned an error"

        doxygen_version = stdout.decode(errors='replace').strip()

        # Validate version string to ensure it looks like Doxygen output
        # Doxygen version is typically like 1.9.4 or 1.8.17
        if not re.match(r'^\d+\.\d+\.\d+', doxygen_version):
            return f"❌ Unexpected Doxygen version format: {doxygen_version}"

        result = f"✅ Doxygen {doxygen_version} is installed and working"
        _DOXYGEN_VERSION_CACHE[doxygen_exe] = result
        return result
    except (FileNotFoundError, OSError):
        return "❌ Doxygen is not installed"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error checking Doxygen: {str(e)}"

@mcp.tool()
async def query_project_reference(
    symbol_name: Optional[str] = None,
    project_path: Optional[str] = None,
) -> str:
    """
    Search for documentation of a specific class, function, or namespace using XML output.
    If symbol_name is not provided, it attempts to use selected text from the active context.
    """
    if not symbol_name:
        context = get_active_context()
        symbol_name = context.get("selected_text")

    if not symbol_name:
        return (
            "❌ Error: No symbol name provided and no text selection "
            "detected in the active context."
        )

    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = os.environ.get("DOXYGEN_XML_DIR")

        if not xml_dir:
            potential_paths = [
                resolved_path / "docs" / "xml",
                resolved_path / "xml",
            ]
            for p in potential_paths:
                p_exists = await asyncio.to_thread(p.exists)
                index_exists = await asyncio.to_thread((p / "index.xml").exists)
                if p_exists and index_exists:
                    xml_dir = str(p)
                    break

        if not xml_dir:
            return (
                "❌ Error: Could not find Doxygen XML directory. "
                "Ensure XML generation is enabled in Doxyfile and "
                "documentation has been generated."
            )

        engine = await DoxygenQueryEngine.create(xml_dir)
        # pylint: disable=no-member
        result = await asyncio.to_thread(engine.query_symbol, symbol_name)

        if not result:
            return f"❓ Symbol '{symbol_name}' not found."

        output = f"🔍 Documentation for {result['kind']} {result['name']}\n"
        output += "=" * len(output) + "\n\n"
        if result["brief"]:
            output += f"Brief: {result['brief']}\n\n"
        if result["detailed"]:
            output += f"Detailed:\n{result['detailed']}\n\n"

        return output
    except ValueError as e:
        return f"❌ {str(e)}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error querying symbol: {str(e)}"

@mcp.tool()
async def get_project_structure(project_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Provide a tree-like overview of the project's documented components.
    """
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return {"error": "Doxygen XML not found. Generate documentation first."}

        engine = await DoxygenQueryEngine.create(xml_dir)

        structure = {
            "project_root": str(resolved_path),
            "classes": engine.list_all_symbols(kind_filter="class"),
            "namespaces": engine.list_all_symbols(kind_filter="namespace"),
            "files": engine.list_all_symbols(kind_filter="file"),
        }

        return structure
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": str(e)}

@mcp.tool()
async def refresh_index(project_path: Optional[str] = None) -> str:
    """
    Trigger a re-scan/parse of Doxygen XML files.
    """
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Doxygen XML not found. Generate documentation first."

        # Re-initializing the engine effectively refreshes the index
        DoxygenQueryEngine.clear_cache(xml_dir)
        await DoxygenQueryEngine.create(xml_dir)
        return "✅ Doxygen index refreshed successfully."
    except ValueError as e:
        return f"❌ {str(e)}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error refreshing index: {str(e)}"

@mcp.tool()
async def get_symbol_at_location(
    file_path: str,
    line_number: int,
    project_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Find symbol context for the IDE's cursor.
    """
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return {"error": "Doxygen XML not found. Generate documentation first."}

        engine = await DoxygenQueryEngine.create(xml_dir)
        # pylint: disable=no-member
        file_symbols = await asyncio.to_thread(engine.get_file_structure, file_path)

        # Simple heuristic: find the symbol that contains this line
        best_match = None
        min_distance = float('inf')

        for symbol in file_symbols:
            loc = symbol.get("location", {})
            if loc.get("file") and Path(loc["file"]).name == Path(file_path).name:
                sym_line = int(loc.get("line", 0))
                if 0 < sym_line <= line_number:
                    distance = line_number - sym_line
                    if distance < min_distance:
                        min_distance = distance
                        best_match = symbol

        return best_match
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": str(e)}

@mcp.tool()
async def query_active_symbol(project_path: Optional[str] = None) -> str:
    """
    Identify and query documentation for the symbol at the current cursor position.
    Uses context provided by the MCP client environment (MCP_ACTIVE_FILE, MCP_CURSOR_LINE).
    """
    context = get_active_context()
    file_path = context.get("active_file")
    line_str = context.get("cursor_line")

    if not file_path or not line_str:
        return (
            "❓ No active file or cursor position detected in the environment. "
            "Ensure your MCP client provides 'MCP_ACTIVE_FILE' and 'MCP_CURSOR_LINE'."
        )

    try:
        line_number = int(line_str)
    except ValueError:
        return f"❌ Invalid cursor line position: {line_str}"

    symbol = await get_symbol_at_location(file_path, line_number, project_path)

    if not symbol or (isinstance(symbol, dict) and "error" in symbol):
        return f"❓ No symbol found at {file_path}:{line_number}."

    return await query_project_reference(symbol["name"], project_path)

@mcp.tool()
async def get_file_structure(
    file_path: str,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve all symbols defined in a specific file.
    """
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return [{"error": "Doxygen XML not found. Generate documentation first."}]

        engine = await DoxygenQueryEngine.create(xml_dir)
        # pylint: disable=no-member
        return await asyncio.to_thread(engine.get_file_structure, file_path)
    except Exception as e:  # pylint: disable=broad-exception-caught
        return [{"error": str(e)}]

def generate_config(args):
    """Generate MCP configuration for various clients."""
    script_path = Path(__file__).resolve()
    # Check if running from source (presence of pyproject.toml in parent)
    repo_root = script_path.parent.parent.parent
    is_source = (repo_root / "pyproject.toml").exists()

    if is_source:
        cmd = "uv"
        cmd_args = ["--directory", str(repo_root), "run", "doxygen-mcp"]
    else:
        # Assuming installed in path and available as command
        cmd = "doxygen-mcp"
        cmd_args = []

    target_path = args.path if args.path else "./"
    abs_path = os.path.abspath(target_path)

    config = {
        "mcpServers": {
            "doxygen-mcp": {
                "command": cmd,
                "args": cmd_args,
                "env": {
                   "DOXYGEN_PROJECT_ROOT": abs_path,
                   "DOXYGEN_ALLOWED_PATHS": f"{os.path.dirname(abs_path)},{abs_path}",
                   "DOXYGEN_XML_DIR": "./docs/xml"
                }
            }
        }
    }

    # Gemini specific format might differ, but for now we output standard MCP
    print(json.dumps(config, indent=2))


def main():
    """Main entry point for the Doxygen MCP server."""
    # Parse arguments for config generation
    parser = argparse.ArgumentParser(description="Doxygen MCP Server", add_help=False)
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("command", nargs="?", choices=["config"], help="Command to run")
    parser.add_argument("--path", type=str, help="Target project path for configuration")
    parser.add_argument("--vscode", action="store_true", help="Generate VS Code config")
    parser.add_argument("--gemini", action="store_true", help="Generate Gemini CLI config")
    parser.add_argument("--cursor", action="store_true", help="Generate Cursor config")

    args, _ = parser.parse_known_args()

    if args.version:
        pkg_v = "unknown"
        if get_package_version is not None:
            try:
                pkg_v = get_package_version("doxygen-mcp")
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        print(f"doxygen-mcp {pkg_v}")
        sys.exit(0)

    if args.command == "config":
        generate_config(args)
        sys.exit(0)

    # Check for Doxygen dependency
    doxygen_exe = get_doxygen_executable()
    try:
        subprocess.run([doxygen_exe, "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning(
            "Doxygen not found at '%s'. Attempting automatic setup...",
            doxygen_exe
        )
        # Use existing check_environment script
        # src/doxygen_mcp/server.py -> src/doxygen_mcp -> src -> root
        script_path = Path(__file__).parent.parent.parent / "scripts" / "check_environment.py"
        if script_path.exists():
            try:
                subprocess.run([sys.executable, str(script_path), "--install"], check=True)
                # Re-verify after install
                subprocess.run([doxygen_exe, "--version"], capture_output=True, check=True)
                logger.info("Doxygen successfully installed and verified.")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Automatic setup failed or Doxygen still not found: %s", e)
                logger.error(
                    "Please install Doxygen manually: https://www.doxygen.nl/download.html"
                )
                # We continue anyway to let MCP start, but tools will fail gracefully.
        else:
            logger.warning("Setup script not found at %s. Skipping auto-setup.", script_path)

    # Only run MCP if not a custom command
    mcp.run()

if __name__ == "__main__":
    main()
