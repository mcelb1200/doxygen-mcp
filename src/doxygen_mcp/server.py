#!/usr/bin/env python3
"""
Doxygen MCP Server - Context Aware Version
"""

import argparse
import asyncio
import json
import logging
import os
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
    get_active_context
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doxygen-mcp")

mcp = FastMCP("Doxygen")

@mcp.tool()
async def get_context_info() -> Dict[str, Any]:
    """
    Get information about the current project context, detected language, and IDE environment.
    """
    try:
        project_path = resolve_project_path()
        language = await detect_primary_language(project_path)
        ide_info = get_ide_environment()
        active_context = get_active_context()

        has_doxyfile = (project_path / "Doxyfile").exists()

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
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def auto_configure(project_name: Optional[str] = None) -> str:
    """
    Automatically detect project settings and create a Doxyfile if one doesn't exist.
    """
    try:
        project_path = resolve_project_path()
        if not project_name:
            project_name = project_path.name

        language = await detect_primary_language(project_path)

        if (project_path / "Doxyfile").exists():
            return f"✨ Project already configured at {project_path}. Detected language: {language}."

        result = await create_doxygen_project(
            project_name=project_name,
            project_path=str(project_path),
            language=language
        )

        return f"🚀 Auto-configured project!\n\n{result}"
    except Exception as e:
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
        safe_project_path = resolve_project_path(project_path)
        if language is None:
            language = await detect_primary_language(safe_project_path)

        if safe_project_path.exists() and not safe_project_path.is_dir():
            return f"❌ Path exists but is not a directory: {safe_project_path}"

        # Create project directory if it doesn't exist
        safe_project_path.mkdir(parents=True, exist_ok=True)

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

        if doxyfile_path.is_symlink():
            return f"❌ Security Error: {doxyfile_path} is a symlink. Cannot overwrite."
        if doxyfile_path.exists():
            return f"❌ Doxyfile already exists at {doxyfile_path}. Use 'auto_configure' or backup first."

        # pylint: disable=no-member
        await asyncio.to_thread(_write_doxyfile_sync, doxyfile_path, config.to_doxyfile())

        # Update .gitignore
        await update_ignore_file(safe_project_path, "docs/")

        return f"✅ Doxygen project '{project_name}' created successfully at {safe_project_path} (Language: {language})"

    except Exception as e:
        return f"❌ Failed to create project: {str(e)}"

@mcp.tool()
async def generate_documentation(
    project_path: Optional[str] = None,
    output_format: str = "html",
    verbose: bool = False,
) -> str:
    """Generate documentation from source code using Doxygen"""
    try:
        safe_project_path = resolve_project_path(project_path)
    except ValueError as e:
        return f"❌ {str(e)}"

    doxyfile_path = safe_project_path / "Doxyfile"
    if not doxyfile_path.exists():
        return "❌ No Doxyfile found. Run 'auto_configure' or 'create_doxygen_project' first."

    doxygen_exe = os.environ.get("DOXYGEN_PATH", "doxygen")

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
            return f"✅ Documentation generated successfully at {safe_project_path / 'docs' / 'html' / 'index.html'}"
        else:
            return f"❌ Documentation generation failed:\n{stderr_text or stdout_text}"

    except Exception as e:
        return f"❌ Error generating documentation: {str(e)}"

def _perform_scan(safe_project_path: Path):
    """Sync helper to scan the filesystem without blocking the event loop"""
    extensions: Dict[str, int] = {}
    total_files = 0

    for root, dirs, files in os.walk(safe_project_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]

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
        safe_project_path = resolve_project_path(project_path)
    except ValueError as e:
        return f"❌ {str(e)}"

    if not safe_project_path.exists():
        return f"❌ Project path does not exist: {safe_project_path}"

    extensions, total_files = await asyncio.to_thread(_perform_scan, safe_project_path)

    sorted_extensions = sorted(extensions.items(), key=lambda x: x[1], reverse=True)
    result_text = f"📁 Project Scan Results: {safe_project_path}\n📊 Total Files Found: {total_files}\n\n📋 Files by Type:\n"
    for ext, count in sorted_extensions[:10]:
        result_text += f"  📄 {ext}: {count} files\n"

    return result_text

@mcp.tool()
async def check_doxygen_install() -> str:
    """Verify that Doxygen is installed and accessible"""
    doxygen_exe = os.environ.get("DOXYGEN_PATH", "doxygen")
    try:
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
        return f"✅ Doxygen {doxygen_version} is installed and working"
    except (FileNotFoundError, OSError):
        return "❌ Doxygen is not installed"
    except Exception as e:
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
        return "❌ Error: No symbol name provided and no text selection detected in the active context."

    try:
        resolved_path = resolve_project_path(project_path)
        xml_dir = os.environ.get("DOXYGEN_XML_DIR")

        if not xml_dir:
            potential_paths = [
                resolved_path / "docs" / "xml",
                resolved_path / "xml",
            ]
            for p in potential_paths:
                if p.exists() and (p / "index.xml").exists():
                    xml_dir = str(p)
                    break

        if not xml_dir:
            return "❌ Error: Could not find Doxygen XML directory. Ensure XML generation is enabled in Doxyfile and documentation has been generated."

        engine = await DoxygenQueryEngine.create(xml_dir)
        result = engine.query_symbol(symbol_name)

        if not result:
            return f"❓ Symbol '{symbol_name}' not found."

        output = f"🔍 Documentation for {result['kind']} {result['name']}\n"
        output += "=" * len(output) + "\n\n"
        if result["brief"]: output += f"Brief: {result['brief']}\n\n"
        if result["detailed"]: output += f"Detailed:\n{result['detailed']}\n\n"

        return output
    except Exception as e:
        return f"❌ Error querying symbol: {str(e)}"

@mcp.tool()
async def get_project_structure(project_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Provide a tree-like overview of the project's documented components.
    """
    try:
        resolved_path = resolve_project_path(project_path)
        xml_dir = _find_xml_dir(resolved_path)

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
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def refresh_index(project_path: Optional[str] = None) -> str:
    """
    Trigger a re-scan/parse of Doxygen XML files.
    """
    try:
        resolved_path = resolve_project_path(project_path)
        xml_dir = _find_xml_dir(resolved_path)

        if not xml_dir:
            return "❌ Doxygen XML not found. Generate documentation first."

        # Re-initializing the engine effectively refreshes the index
        DoxygenQueryEngine.clear_cache(xml_dir)
        await DoxygenQueryEngine.create(xml_dir)
        return "✅ Doxygen index refreshed successfully."
    except Exception as e:
        return f"❌ Error refreshing index: {str(e)}"

@mcp.tool()
async def get_symbol_at_location(file_path: str, line_number: int, project_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Find symbol context for the IDE's cursor.
    """
    try:
        resolved_path = resolve_project_path(project_path)
        xml_dir = _find_xml_dir(resolved_path)

        if not xml_dir:
            return {"error": "Doxygen XML not found. Generate documentation first."}

        engine = await DoxygenQueryEngine.create(xml_dir)
        file_symbols = engine.get_file_structure(file_path)

        # Simple heuristic: find the symbol that contains this line
        best_match = None
        min_distance = float('inf')

        for symbol in file_symbols:
            loc = symbol.get("location", {})
            if loc.get("file") and Path(loc["file"]).name == Path(file_path).name:
                sym_line = int(loc.get("line", 0))
                if sym_line > 0 and sym_line <= line_number:
                    distance = line_number - sym_line
                    if distance < min_distance:
                        min_distance = distance
                        best_match = symbol

        return best_match
    except Exception as e:
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
        return "❓ No active file or cursor position detected in the environment. Ensure your MCP client provides 'MCP_ACTIVE_FILE' and 'MCP_CURSOR_LINE'."

    try:
        line_number = int(line_str)
    except ValueError:
        return f"❌ Invalid cursor line position: {line_str}"

    symbol = await get_symbol_at_location(file_path, line_number, project_path)

    if not symbol or (isinstance(symbol, dict) and "error" in symbol):
        return f"❓ No symbol found at {file_path}:{line_number}."

    return await query_project_reference(symbol["name"], project_path)

@mcp.tool()
async def get_file_structure(file_path: str, project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve all symbols defined in a specific file.
    """
    try:
        resolved_path = resolve_project_path(project_path)
        xml_dir = _find_xml_dir(resolved_path)

        if not xml_dir:
            return [{"error": "Doxygen XML not found. Generate documentation first."}]

        engine = await DoxygenQueryEngine.create(xml_dir)
        return engine.get_file_structure(file_path)
    except Exception as e:
        return [{"error": str(e)}]

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

    if args.gemini:
        # Gemini specific format might differ, but for now we output standard MCP
        print(json.dumps(config, indent=2))
    else:
        print(json.dumps(config, indent=2))


def main():
    # Parse arguments for config generation
    parser = argparse.ArgumentParser(description="Doxygen MCP Server", add_help=False)
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("command", nargs="?", choices=["config"], help="Command to run")
    parser.add_argument("--path", type=str, help="Target project path for configuration")
    parser.add_argument("--vscode", action="store_true", help="Generate VS Code config")
    parser.add_argument("--gemini", action="store_true", help="Generate Gemini CLI config")
    parser.add_argument("--cursor", action="store_true", help="Generate Cursor config")

    args, unknown = parser.parse_known_args()

    if args.version:
        pkg_v = "unknown"
        if get_package_version is not None:
            try:
                pkg_v = get_package_version("doxygen-mcp")
            except:
                pass
        print(f"doxygen-mcp {pkg_v}")
        sys.exit(0)

    if args.command == "config":
        generate_config(args)
        sys.exit(0)

    # Check for Doxygen dependency
    doxygen_exe = os.environ.get("DOXYGEN_PATH", "doxygen")
    try:
        subprocess.run([doxygen_exe, "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning(f"Doxygen not found at '{doxygen_exe}'. Attempting automatic setup...")
        # Use existing check_environment script
        # src/doxygen_mcp/server.py -> src/doxygen_mcp -> src -> root
        script_path = Path(__file__).parent.parent.parent / "scripts" / "check_environment.py"
        if script_path.exists():
            try:
                subprocess.run([sys.executable, str(script_path), "--install"], check=True)
                # Re-verify after install
                subprocess.run([doxygen_exe, "--version"], capture_output=True, check=True)
                logger.info("Doxygen successfully installed and verified.")
            except Exception as e:
                logger.error(f"Automatic setup failed or Doxygen still not found: {e}")
                logger.error("Please install Doxygen manually: https://www.doxygen.nl/download.html")
                # We continue anyway to let MCP start, but tools will fail gracefully.
        else:
             logger.warning(f"Setup script not found at {script_path}. Skipping auto-setup.")

    # Only run MCP if not a custom command
    mcp.run()

if __name__ == "__main__":
    main()
