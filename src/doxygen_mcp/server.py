#!/usr/bin/env python3
"""
Doxygen MCP Server - Context Aware Version
"""

import argparse
import asyncio
import glob
import json
import logging
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_package_version
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import watchdog.events
    import watchdog.observers

    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

import shutil

# MCP server imports
from mcp.server.fastmcp import FastMCP

from .config import DoxygenConfig
from .funnel import minify_xml_file, setup_funnel
from .git_tracker import get_file_timeline
from .query_engine import DoxygenQueryEngine
from .types import MCPResult
from .utils import (
    detect_primary_language,
    get_active_context,
    get_doxygen_executable,
    get_ide_environment,
    load_project_config,
    resolve_project_path,
    update_ignore_file,
)
from .version import __version__

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doxygen-mcp")

mcp = FastMCP("Doxygen")

# Global Output Compression (Token Crusher Middleware)
from functools import wraps

from .caveman import compress_payload

is_pytest = "pytest" in sys.modules
compress_env_val = os.environ.get("DOXYGEN_COMPRESS_OUTPUT")
if compress_env_val is not None:
    SHOULD_COMPRESS = compress_env_val.lower() not in ("false", "0", "no", "off")
else:
    SHOULD_COMPRESS = not is_pytest

use_mcp_result_env = os.environ.get("DOXYGEN_USE_MCP_RESULT")
if use_mcp_result_env is not None:
    SHOULD_WRAP_MCP_RESULT = use_mcp_result_env.lower() not in (
        "false",
        "0",
        "no",
        "off",
    )
else:
    SHOULD_WRAP_MCP_RESULT = not is_pytest


def wrap_in_mcp_result(res: Any) -> Any:
    if not SHOULD_WRAP_MCP_RESULT:
        return res
    if isinstance(res, MCPResult):
        return res

    # If the tool returned a dictionary or list containing an error key
    if isinstance(res, dict) and "error" in res:
        return MCPResult(success=False, error=str(res["error"]))
    if (
        isinstance(res, list)
        and len(res) == 1
        and isinstance(res[0], dict)
        and "error" in res[0]
    ):
        return MCPResult(success=False, error=str(res[0]["error"]))

    if isinstance(res, str):
        res_stripped = res.strip()
        if (
            res_stripped.startswith("❌")
            or res_stripped.startswith("[ERROR]")
            or res_stripped.startswith("Security Error")
        ):
            return MCPResult(success=False, error=res)
        elif res_stripped.startswith("⚠️") or res_stripped.startswith("[WARNING]"):
            return MCPResult(success=False, error=res)
        elif (
            res_stripped.startswith("✅")
            or res_stripped.startswith("[SUCCESS]")
            or res_stripped.startswith("📁")
            or res_stripped.startswith("ℹ️")
        ):
            return MCPResult(success=True, message=res)
        else:
            return MCPResult(success=True, data=res)

    return MCPResult(success=True, data=res)


original_tool = mcp.tool


def token_crusher_tool(*args, **kwargs):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*f_args, **f_kwargs):
                try:
                    res = await func(*f_args, **f_kwargs)
                    wrapped = wrap_in_mcp_result(res)
                except Exception as e:
                    if SHOULD_WRAP_MCP_RESULT:
                        wrapped = MCPResult(success=False, error=str(e))
                    else:
                        raise e

                if SHOULD_COMPRESS:
                    return compress_payload(wrapped)
                return wrapped

            return original_tool(*args, **kwargs)(async_wrapper)
        else:

            @wraps(func)
            def sync_wrapper(*f_args, **f_kwargs):
                try:
                    res = func(*f_args, **f_kwargs)
                    wrapped = wrap_in_mcp_result(res)
                except Exception as e:
                    if SHOULD_WRAP_MCP_RESULT:
                        wrapped = MCPResult(success=False, error=str(e))
                    else:
                        raise e

                if SHOULD_COMPRESS:
                    return compress_payload(wrapped)
                return wrapped

            return original_tool(*args, **kwargs)(sync_wrapper)

    return decorator


mcp.tool = token_crusher_tool  # type: ignore

# Cache for Doxygen version check
_DOXYGEN_VERSION_CACHE: Dict[str, str] = {}

if HAS_WATCHDOG:

    class DoxygenConfigWatcher(watchdog.events.FileSystemEventHandler):
        def on_modified(self, event):
            global _DOXYGEN_VERSION_CACHE
            if not event.is_directory:
                src_name = os.path.basename(event.src_path)
                if src_name == "Doxyfile" or "doxygen" in src_name.lower():
                    _DOXYGEN_VERSION_CACHE.clear()

else:

    class DoxygenConfigWatcher:  # type: ignore
        pass


_watcher_started = False


def start_watchdog():
    global _watcher_started
    if _watcher_started or not HAS_WATCHDOG:
        return
    _watcher_started = True
    try:
        # Use daemon=True observer to not block main thread exit
        observer = watchdog.observers.Observer()
        observer.daemon = True
        event_handler = DoxygenConfigWatcher()
        # Watch only current directory non-recursively for Doxyfile updates
        observer.schedule(event_handler, path=".", recursive=False)
        observer.start()
    except Exception as e:
        logger.warning("Failed to start Doxyfile watchdog: %s", e)


start_watchdog()

# Common directories to skip for performance during filesystem scans
SCAN_SKIP_DIRS = {
    "node_modules",
    "build",
    "dist",
    "target",
    "venv",
    "env",
    "__pycache__",
    "bower_components",
    "extern",
    "external",
    "vendor",
}


def _find_xml_dir(resolved_path: Path) -> Optional[str]:
    """
    Find the Doxygen XML directory with preference for:
    1. DOXYGEN_XML_DIR env var (absolute or relative)
    2. doxygen_mcp.json config in project root
    3. Standard locations within project root
    """
    xml_dir_env = os.environ.get("DOXYGEN_XML_DIR")
    if xml_dir_env:
        path = Path(xml_dir_env)
        if not path.is_absolute():
            path = resolved_path / path

        if path.exists() and (path / "index.xml").exists():
            return str(path.absolute())

    # Check doxygen_mcp.json
    config_data = load_project_config(resolved_path)
    xml_dir_val = config_data.get("xml_dir")
    if isinstance(xml_dir_val, str) and xml_dir_val.strip():
        path = Path(xml_dir_val.strip())
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


async def _minify_all_xml(xml_dir: str) -> None:
    """Run SNR filter on all XML files in parallel with bounded concurrency."""
    xml_files = glob.glob(os.path.join(xml_dir, "*.xml"))
    if not xml_files:
        return

    # Use a semaphore to limit the number of concurrent threads to avoid pool exhaustion
    semaphore = asyncio.Semaphore(10)

    async def _sem_minify(file_path: str) -> bool:
        async with semaphore:
            return await asyncio.to_thread(minify_xml_file, file_path)

    await asyncio.gather(*[_sem_minify(f) for f in xml_files])


_UPDATE_CHECK_CACHE: Optional[str] = None


def _check_for_updates_sync() -> Optional[str]:
    """Synchronous version checker using urllib."""
    global _UPDATE_CHECK_CACHE
    if _UPDATE_CHECK_CACHE is not None:
        return _UPDATE_CHECK_CACHE if _UPDATE_CHECK_CACHE != "" else None

    import json
    import urllib.request

    try:
        url = "https://pypi.org/pypi/doxygen-mcp/json"
        req = urllib.request.Request(
            url, headers={"User-Agent": f"doxygen-mcp/{__version__}"}
        )
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                latest_version = data["info"]["version"]

                def parse_ver(v):
                    return tuple(
                        map(
                            int,
                            v.split("+")[0]
                            .split("rc")[0]
                            .split("a")[0]
                            .split("b")[0]
                            .split("."),
                        )
                    )

                if parse_ver(latest_version) > parse_ver(__version__):
                    _UPDATE_CHECK_CACHE = latest_version
                    return latest_version
    except Exception:
        pass

    _UPDATE_CHECK_CACHE = ""
    return None


@mcp.tool()
async def get_context_info() -> Dict[str, Any]:
    """Get project context, language, and IDE info."""
    try:
        # pylint: disable=no-member
        project_path = await asyncio.to_thread(resolve_project_path)
        language = await asyncio.to_thread(detect_primary_language, project_path)
        ide_info = await asyncio.to_thread(get_ide_environment)
        active_context = get_active_context()

        has_doxyfile = await asyncio.to_thread((project_path / "Doxyfile").exists)

        # Check for updates in the background
        update_available = None
        try:
            update_available = await asyncio.to_thread(_check_for_updates_sync)
        except Exception:
            pass

        res = {
            "project_root": str(project_path),
            "detected_language": language,
            "ide_environment": ide_info,
            "active_context": active_context,
            "doxygen_status": {
                "has_doxyfile": has_doxyfile,
                "config_path": str(project_path / "Doxyfile") if has_doxyfile else None,
            },
        }
        if update_available:
            logger.warning(
                "⚠️ UPDATE AVAILABLE: A newer version of doxygen-mcp (v%s) is available. Run 'uv tool upgrade doxygen-mcp' to update.",
                update_available,
            )
            res["update_warning"] = (
                f"⚠️ UPDATE AVAILABLE: A newer version of doxygen-mcp (v{update_available}) is available. Run 'uv tool upgrade doxygen-mcp' to update."
            )
        return res
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": str(e)}


@mcp.tool(name="doxy_context")
async def doxy_context() -> Dict[str, Any]:
    """Legacy wrapper for get_context_info."""
    return await get_context_info()


@mcp.tool()
async def auto_configure(project_name: Optional[str] = None) -> str:
    """Auto-detect settings and create Doxyfile."""
    try:
        # pylint: disable=no-member
        project_path = await asyncio.to_thread(resolve_project_path)
        if not project_name:
            project_name = project_path.name

        language = await asyncio.to_thread(detect_primary_language, project_path)

        doxyfile_exists = await asyncio.to_thread((project_path / "Doxyfile").exists)
        if doxyfile_exists:
            return f"✅ Project already configured at {project_path}. Detected language: {language}."

        result = await create_doxygen_project(
            project_name=project_name, project_path=str(project_path), language=language
        )

        return f"ℹ️ Auto-configured project!\n\n{result}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Auto-configuration failed: {str(e)}"


@mcp.tool(name="doxy_config")
async def doxy_config(project_name: Optional[str] = None) -> str:
    """Legacy wrapper for auto_configure."""
    return await auto_configure(project_name)


def _write_doxyfile_sync(path: Path, content: str) -> None:
    """Helper to write Doxyfile synchronously."""
    with open(path, "w", encoding="utf-8") as f:
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
    # pylint: disable=too-many-arguments, too-many-locals, too-many-positional-arguments
    """Init new Doxygen project config."""
    try:
        # Resolve project path and detect language if not provided
        # pylint: disable=no-member
        safe_project_path = await asyncio.to_thread(resolve_project_path, project_path)
        if language is None:
            language = await asyncio.to_thread(
                detect_primary_language, safe_project_path
            )

        if await asyncio.to_thread(
            safe_project_path.exists
        ) and not await asyncio.to_thread(safe_project_path.is_dir):
            return f"❌ Failed to create project: Path exists but is not a directory: {safe_project_path}"

        # Create project directory if it doesn't exist
        await asyncio.to_thread(safe_project_path.mkdir, parents=True, exist_ok=True)

        # Create configuration based on language
        config = DoxygenConfig(
            project_name=project_name,
            output_directory=str(safe_project_path / "docs"),
            input_paths=[str(safe_project_path)],
            recursive=include_subdirs,
            extract_private=extract_private,
            exclude_symlinks=not follow_symlinks,
        )

        # Language-specific optimizations
        lang_settings: Dict[str, Dict[str, Any]] = {
            "c": {"optimize_output_for_c": True, "file_patterns": ["*.c", "*.h"]},
            "cpp": {
                "file_patterns": ["*.cpp", "*.hpp", "*.cc", "*.hh", "*.cxx", "*.hxx"]
            },
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

        if await asyncio.to_thread(doxyfile_path.is_symlink):
            return f"❌ Failed to create project: Security Error: {doxyfile_path} is a symlink. Cannot overwrite."
        if await asyncio.to_thread(doxyfile_path.exists):
            return (
                f"❌ Failed to create project: Doxyfile already exists at {doxyfile_path}. "
                "Use 'doxy_config' or backup first."
            )

        # pylint: disable=no-member
        await asyncio.to_thread(
            _write_doxyfile_sync, doxyfile_path, config.to_doxyfile()
        )

        # Update .gitignore
        await update_ignore_file(safe_project_path, "docs/xml/")

        return (
            f"✅ Doxygen project '{project_name}' created successfully "
            f"at {safe_project_path} (Language: {language})"
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Failed to create project: {str(e)}"


@mcp.tool(name="doxy_create")
async def doxy_create(
    project_name: str,
    project_path: Optional[str] = None,
    language: Optional[str] = None,
    include_subdirs: bool = True,
    extract_private: bool = False,
    follow_symlinks: bool = False,
) -> str:
    """Legacy wrapper for create_doxygen_project."""
    return await create_doxygen_project(
        project_name=project_name,
        project_path=project_path,
        language=language,
        include_subdirs=include_subdirs,
        extract_private=extract_private,
        follow_symlinks=follow_symlinks,
    )


@mcp.tool()
async def generate_documentation(
    project_path: Optional[str] = None,
) -> str:
    """Generate docs using Doxygen."""
    try:
        safe_project_path = await _get_project_path(project_path)
    except ValueError as e:
        return f"❌ Error: {str(e)}"

    doxyfile_path = safe_project_path / "Doxyfile"
    doxyfile_exists = await asyncio.to_thread(doxyfile_path.exists)
    if not doxyfile_exists:
        return "❌ No Doxyfile found. Run 'auto_configure' or 'create_doxygen_project' first."

    doxygen_exe = get_doxygen_executable()

    try:
        # Run Doxygen asynchronously with timeout
        process = await asyncio.create_subprocess_exec(
            doxygen_exe,
            str(doxyfile_path),
            cwd=str(safe_project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # Set a 300-second timeout to prevent indefinite hangs
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=300.0
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass  # Process already finished
            await process.wait()
            return "❌ Error: Documentation generation timed out after 300 seconds."

        stdout_text = stdout.decode(errors="replace") if stdout else ""
        stderr_text = stderr.decode(errors="replace") if stderr else ""

        if process.returncode == 0:
            # Clear all caches as documentation has been regenerated
            DoxygenQueryEngine.clear_cache()
            return (
                "✅ Documentation generated successfully at "
                f"{safe_project_path / 'docs' / 'html' / 'index.html'}"
            )

        return (
            f"❌ Error: Documentation generation failed:\n{stderr_text or stdout_text}"
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error generating documentation: {str(e)}"


@mcp.tool(name="doxy_generate")
async def doxy_generate(
    project_path: Optional[str] = None,
) -> str:
    """Legacy wrapper for generate_documentation."""
    return await generate_documentation(project_path)


def _perform_scan(safe_project_path: Path):
    """Sync helper to scan the filesystem without blocking the event loop"""
    extensions: Dict[str, int] = {}
    total_files = 0

    for _, dirs, files in os.walk(safe_project_path):
        # Skip hidden directories and common large/irrelevant folders
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SCAN_SKIP_DIRS]

        for file in files:
            if file.startswith("."):
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
    """Analyze project structure and files."""
    try:
        safe_project_path = await _get_project_path(project_path)
    except ValueError as e:
        return f"❌ Error: {str(e)}"

    path_exists = await asyncio.to_thread(safe_project_path.exists)
    if not path_exists:
        return f"❌ Project path does not exist: {safe_project_path}"

    # pylint: disable=no-member
    extensions, total_files = await asyncio.to_thread(_perform_scan, safe_project_path)

    sorted_extensions = sorted(extensions.items(), key=lambda x: x[1], reverse=True)
    lines = [
        f"📁 Project Scan Results: {safe_project_path}",
        f"[INFO] Total Files Found: {total_files}",
        "",
        "Files by Type:",
    ]
    for ext, count in sorted_extensions[:10]:
        lines.append(f"  - {ext}: {count} files")

    return "\n".join(lines) + "\n"


@mcp.tool(name="doxy_scan")
async def doxy_scan(
    project_path: Optional[str] = None,
) -> str:
    """Legacy wrapper for scan_project."""
    return await scan_project(project_path)


@mcp.tool()
async def check_doxygen_install() -> str:
    # pylint: disable=too-many-return-statements
    """Verify Doxygen installation."""
    try:
        doxygen_exe = get_doxygen_executable()
        if doxygen_exe in _DOXYGEN_VERSION_CACHE:
            return _DOXYGEN_VERSION_CACHE[doxygen_exe]

        process = await asyncio.create_subprocess_exec(
            doxygen_exe,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            return "❌ Error: Doxygen check timed out"

        if process.returncode != 0:
            return "❌ Error: Doxygen is not installed or returned an error"

        doxygen_version = stdout.decode(errors="replace").strip()

        # Validate version string to ensure it looks like Doxygen output
        # Doxygen version is typically like 1.9.4 or 1.8.17
        if not re.match(r"^\d+\.\d+\.\d+", doxygen_version):
            return f"❌ Unexpected Doxygen version format: {doxygen_version}"

        result = f"✅ Doxygen {doxygen_version} is installed and working"
        _DOXYGEN_VERSION_CACHE[doxygen_exe] = result
        return result
    except (FileNotFoundError, OSError):
        return "❌ Error: Doxygen is not installed"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error checking Doxygen: {str(e)}"


@mcp.tool(name="doxy_check")
async def doxy_check() -> str:
    """Legacy wrapper for check_doxygen_install."""
    return await check_doxygen_install()


@mcp.tool()
async def query_project_reference(
    symbol_name: Optional[str] = None,
    project_path: Optional[str] = None,
) -> str:
    # pylint: disable=too-many-locals
    """Search documentation for a symbol."""
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
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

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
            return f"⚠️ Symbol '{symbol_name}' not found in index. Ensure it is committed or indexed."

        timeline = ""
        filepath = result.get("location", {}).get("file", "")
        if filepath:
            full_path = resolved_path / filepath
            timeline = get_file_timeline(str(full_path), is_indexed=True) + "\n\n"

        header = f"ℹ️ Documentation for {result['kind']} {result['name']}"
        lines = [timeline.strip(), "", header, "=" * (len(header) + 1), ""]
        if result["brief"]:
            lines.append(f"Brief: {result['brief']}\n")
        if result["detailed"]:
            lines.append(f"Detailed:\n{result['detailed']}\n")

        return "\n".join(lines).strip() + "\n"
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error querying symbol: {str(e)}"


@mcp.tool(name="doxy_query")
async def doxy_query(
    symbol_name: Optional[str] = None,
    project_path: Optional[str] = None,
) -> str:
    """Legacy wrapper for query_project_reference."""
    return await query_project_reference(symbol_name, project_path)


@mcp.tool()
async def semantic_search(
    query: str,
    limit: int = 5,
    project_path: Optional[str] = None,
) -> str:
    """Semantic search across docs and symbols."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Error: Could not find Doxygen XML directory."

        engine = await DoxygenQueryEngine.create(xml_dir)
        # pylint: disable=no-member
        results = await asyncio.to_thread(engine.semantic_search, query, limit)

        if not results:
            return f"ℹ️ No semantic matches found for '{query}'."

        if len(results) > 0 and "error" in results[0]:
            return f"❌ Error: {results[0]['error']}"

        lines = [
            f"ℹ️ Semantic Search Results for '{query}' (Limit: {limit})",
            "=" * 60,
            "",
        ]

        for r in results:
            lines.append(f"- {r['kind'].upper()}: {r['name']}")
            if r.get("filepath"):
                full_path = resolved_path / r["filepath"]
                # Compact timeline for search results
                timeline = get_file_timeline(str(full_path), is_indexed=True).replace(
                    "\n", " | "
                )
                lines.append(f"   {timeline}")
            if r.get("brief"):
                # Truncate brief if too long
                brief = (
                    r["brief"][:200] + "..." if len(r["brief"]) > 200 else r["brief"]
                )
                lines.append(f"   Brief: {brief}")
            lines.append(f"   Relevance Score: {r['rank']}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Semantic search failed: {str(e)}"


@mcp.tool(name="doxy_search")
async def doxy_search(
    query: str,
    limit: int = 5,
    project_path: Optional[str] = None,
) -> str:
    """Legacy wrapper for semantic_search."""
    return await semantic_search(query, limit, project_path)


@mcp.tool()
async def get_symbol_usage(
    symbol_name: str,
    project_path: Optional[str] = None,
) -> str:
    """Get call graph and inheritance for symbol."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Error: Could not find Doxygen XML directory."

        engine = await DoxygenQueryEngine.create(xml_dir)
        # pylint: disable=no-member
        result = await asyncio.to_thread(engine.get_symbol_connections, symbol_name)

        if not result:
            return f"⚠️ Symbol '{symbol_name}' not found."

        if "error" in result:
            return f"❌ Error: {result['error']}"

        output = f"ℹ️ Connection Graph for {result['kind']} {result['name']}\n"
        output += "=" * len(output) + "\n\n"

        if result.get("base_classes"):
            output += f"Inherits from: {', '.join(result['base_classes'])}\n"
        if result.get("derived_classes"):
            output += f"Inherited by: {', '.join(result['derived_classes'])}\n\n"

        if not result.get("members"):
            output += "No member-level references found.\n"
            return output

        for member in result["members"]:
            output += f"- {member['kind']} {member['name']}:\n"
            if member["references"]:
                output += f"  Calls: {', '.join(member['references'])}\n"
            if member["referencedby"]:
                output += f"  Called by: {', '.join(member['referencedby'])}\n"

        return output
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error querying symbol usage: {str(e)}"


@mcp.tool(name="doxy_references")
async def doxy_references(
    symbol_name: str, project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Find all call sites / occurrences of a symbol (file and line) across workspace."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return [{"error": "Doxygen XML not found. Generate documentation first."}]

        engine = await DoxygenQueryEngine.create(xml_dir)
        return await asyncio.to_thread(engine.find_references, symbol_name)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(name="doxy_rename_impact")
async def doxy_rename_impact(
    symbol_name: str, project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Analyze impact of renaming a symbol. Lists definition sites, call sites, and subclasses that will break."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return {"error": "Doxygen XML not found. Generate documentation first."}

        engine = await DoxygenQueryEngine.create(xml_dir)

        definitions = await asyncio.to_thread(
            engine.find_symbol_definitions, symbol_name
        )
        references = await asyncio.to_thread(engine.find_references, symbol_name)

        if not definitions:
            return {
                "symbol": symbol_name,
                "found": False,
                "message": f"Symbol '{symbol_name}' not found in Doxygen index.",
            }

        defs_list = []
        for d in definitions:
            loc = d.get("location") or {}
            defs_list.append(
                {
                    "name": d["name"],
                    "kind": d["kind"],
                    "file": loc.get("file", "unknown"),
                    "line": int(loc.get("line") or 1),
                }
            )

        calls_list = []
        inheritance_list = []

        for r in references:
            if "inherits from" in r.get("content", ""):
                inheritance_list.append(
                    {"subclass": r["caller"], "file": r["file"], "line": r["line"]}
                )
            else:
                calls_list.append(
                    {
                        "caller": r["caller"],
                        "file": r["file"],
                        "line": r["line"],
                        "line_content": r["content"],
                    }
                )

        return {
            "symbol": symbol_name,
            "found": True,
            "definitions": defs_list,
            "references": calls_list,
            "inheritance_impact": inheritance_list,
            "total_impacted_files": len(
                set(
                    [d["file"] for d in defs_list if d["file"] != "unknown"]
                    + [c["file"] for c in calls_list]
                    + [i["file"] for i in inheritance_list]
                )
            ),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(name="doxy_parity_check")
async def doxy_parity_check(project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scan codebase for Doxygen-to-code parity mismatches (mismatched, redundant, or missing @param tags)."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return [{"error": "Doxygen XML not found. Generate documentation first."}]

        from .auditor import check_doxygen_parity

        engine = await DoxygenQueryEngine.create(xml_dir)
        return await asyncio.to_thread(check_doxygen_parity, engine)
    except Exception as e:
        return [{"error": str(e)}]


def _merge_index_xml_sync(main_index_path: Path, temp_index_path: Path) -> None:
    """Helper to merge temporary index.xml into main index.xml."""
    import defusedxml.ElementTree as ET

    try:
        main_tree = ET.parse(main_index_path)
        main_root = main_tree.getroot()

        temp_tree = ET.parse(temp_index_path)
        temp_root = temp_tree.getroot()

        if main_root is None or temp_root is None:
            return

        temp_compounds = temp_root.findall("compound")
        if temp_compounds:
            for temp_compound in temp_compounds:
                refid = temp_compound.get("refid")
                if refid:
                    existing_nodes = main_root.findall(f"./compound[@refid='{refid}']")
                    if existing_nodes:
                        for existing in existing_nodes:
                            main_root.remove(existing)
                    main_root.append(temp_compound)

        main_tree.write(main_index_path, encoding="utf-8", xml_declaration=True)
    except Exception as err:
        logger.error("Failed to merge index.xml: %s", err)


async def _process_delta_xml_files(temp_xml_out: Path, xml_dest_dir: Path) -> int:
    """Helper to minify and copy generated XML files."""
    from .funnel import minify_xml_file

    temp_xml_files = list(temp_xml_out.glob("*.xml"))
    copied_count = 0
    for temp_file in temp_xml_files:
        if temp_file.name in ("index.xml", "index.xsd", "compound.xsd", "xml.xsd"):
            continue

        await asyncio.to_thread(minify_xml_file, str(temp_file))
        dest_file = xml_dest_dir / temp_file.name
        await asyncio.to_thread(shutil.copy2, temp_file, dest_file)
        copied_count += 1
    return copied_count


async def _generate_delta_xml(
    resolved_path: Path, target_path: Path, delta_temp: Path
) -> None:
    """Helper to generate delta XML for a specific path."""
    base_doxyfile = "Doxyfile"
    if (resolved_path / "Doxyfile.fast").exists():
        base_doxyfile = "Doxyfile.fast"
    elif not (resolved_path / "Doxyfile").exists():
        doxyfile_path = resolved_path / "Doxyfile"
        doxygen_exe = get_doxygen_executable()
        await asyncio.create_subprocess_exec(
            doxygen_exe,
            "-g",
            str(doxyfile_path),
            cwd=str(resolved_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    temp_doxyfile_content = f"""# Temporary Doxyfile for Delta Refresh
@INCLUDE               = {base_doxyfile}
INPUT                  = "{target_path}"
OUTPUT_DIRECTORY       = "{delta_temp}"
GENERATE_XML           = YES
GENERATE_HTML          = NO
GENERATE_LATEX         = NO
XML_OUTPUT             = xml
"""
    temp_doxyfile_path = delta_temp / "Doxyfile.temp"
    await asyncio.to_thread(
        temp_doxyfile_path.write_text, temp_doxyfile_content, encoding="utf-8"
    )

    doxygen_exe = get_doxygen_executable()
    process = await asyncio.create_subprocess_exec(
        doxygen_exe,
        str(temp_doxyfile_path),
        cwd=str(resolved_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
    except asyncio.TimeoutError as exc:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        await process.wait()
        raise TimeoutError("Doxygen delta generation timed out.") from exc

    if process.returncode != 0:
        stderr_text = stderr.decode(errors="replace") if stderr else ""
        raise RuntimeError(f"Doxygen delta generation failed:\n{stderr_text}")


@mcp.tool(name="doxy_refresh_delta")
async def doxy_refresh_delta(
    file_or_dir_path: str, project_path: Optional[str] = None
) -> str:
    """Incrementally update Doxygen documentation for a single file or subdirectory."""
    import shutil

    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Error: Doxygen XML directory not found. Generate documentation first using 'doxy_generate'."

        target_path = Path(file_or_dir_path)
        if not target_path.is_absolute():
            target_path = (resolved_path / target_path).resolve()

        try:
            target_path.relative_to(resolved_path)
        except ValueError:
            return f"❌ Security Error: Path '{file_or_dir_path}' is outside the project root."

        if not target_path.exists():
            return f"❌ Error: Target path '{file_or_dir_path}' does not exist."

        delta_temp = resolved_path / ".doxy_delta_temp"
        if delta_temp.exists():
            await asyncio.to_thread(shutil.rmtree, delta_temp, ignore_errors=True)
        await asyncio.to_thread(delta_temp.mkdir, exist_ok=True)

        temp_xml_out = delta_temp / "xml"
        await asyncio.to_thread(temp_xml_out.mkdir, exist_ok=True)

        try:
            await _generate_delta_xml(resolved_path, target_path, delta_temp)
        except TimeoutError as e:
            return f"❌ Error: {str(e)}"
        except RuntimeError as e:
            return f"❌ Error: {str(e)}"

        xml_dest_dir = Path(xml_dir)
        copied_count = await _process_delta_xml_files(temp_xml_out, xml_dest_dir)

        temp_index_path = temp_xml_out / "index.xml"
        main_index_path = xml_dest_dir / "index.xml"

        if temp_index_path.exists():
            if not main_index_path.exists():
                await asyncio.to_thread(shutil.copy2, temp_index_path, main_index_path)
            else:
                await asyncio.to_thread(
                    _merge_index_xml_sync, main_index_path, temp_index_path
                )

        await asyncio.to_thread(shutil.rmtree, delta_temp, ignore_errors=True)

        DoxygenQueryEngine.clear_cache(xml_dir)
        await DoxygenQueryEngine.create(xml_dir)

        return f"✅ Delta refresh completed successfully. Updated {copied_count} files."
    except Exception as e:
        return f"❌ Delta refresh failed: {str(e)}"


@mcp.tool(name="doxy_skeleton")
async def doxy_skeleton(file_path: str, project_path: Optional[str] = None) -> str:
    """Generate a skeletal version of the source file (signatures only, bodies stripped)."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Doxygen XML not found. Generate documentation first."

        engine = await DoxygenQueryEngine.create(xml_dir)
        return await asyncio.to_thread(engine.get_file_skeleton, file_path)
    except Exception as e:
        return f"❌ Error generating skeleton: {str(e)}"


@mcp.tool(name="doxy_virtual_diff")
async def doxy_virtual_diff(project_path: Optional[str] = None) -> Dict[str, Any]:
    """Track active working-tree edits and provide exact signature differences."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return {"error": "❌ Doxygen XML not found. Generate documentation first."}

        engine = await DoxygenQueryEngine.create(xml_dir)
        return await asyncio.to_thread(engine.get_virtual_diff, str(resolved_path))
    except Exception as e:
        return {"error": f"❌ Error in doxy_virtual_diff: {str(e)}"}


@mcp.tool(name="doxy_trace_path")
async def doxy_trace_path(
    entry_symbol: str, max_depth: int = 3, project_path: Optional[str] = None
) -> str:
    """Crawl call graphs sequentially along a call path starting from entry_symbol."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Doxygen XML not found. Generate documentation first."

        engine = await DoxygenQueryEngine.create(xml_dir)
        return await asyncio.to_thread(engine.trace_call_path, entry_symbol, max_depth)
    except Exception as e:
        return f"❌ Error in doxy_trace_path: {str(e)}"


@mcp.tool()
async def configure_repo_context(
    project_path: Optional[str] = None,
) -> str:
    """Onboard repo to context funnel."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)

        # pylint: disable=no-member
        success, msg = await asyncio.to_thread(setup_funnel, str(resolved_path))

        if success:
            return f"✅ {msg}"
        return f"❌ {msg}"
    except Exception as e:
        return f"❌ Error configuring repository: {str(e)}"


@mcp.tool(name="doxy_onboard")
async def doxy_onboard(
    project_path: Optional[str] = None,
) -> str:
    """Legacy wrapper for configure_repo_context."""
    return await configure_repo_context(project_path)


@mcp.tool()
async def get_project_structure(project_path: Optional[str] = None) -> Dict[str, Any]:
    """Get tree overview of documented components."""
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


@mcp.tool(name="doxy_structure")
async def doxy_structure(project_path: Optional[str] = None) -> Dict[str, Any]:
    """Legacy wrapper for get_project_structure."""
    return await get_project_structure(project_path)


@mcp.tool()
async def refresh_index(project_path: Optional[str] = None) -> str:
    """Re-scan and parse Doxygen XML."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        if not xml_dir:
            return "❌ Error: Doxygen XML not found. Generate documentation first."

        # Run Doxygen build and SNR filter
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["doxygen", "Doxyfile.fast"],
                cwd=resolved_path,
                check=True,
                capture_output=True,
                shell=False,
            )

            # Run SNR filter in parallel with bounded concurrency
            await _minify_all_xml(xml_dir)

        except Exception as build_err:
            return f"❌ Failed to rebuild Doxygen index: {build_err}"

        # Re-initializing the engine effectively refreshes the index
        DoxygenQueryEngine.clear_cache(xml_dir)
        await DoxygenQueryEngine.create(xml_dir)
        return "✅ Doxygen index rebuilt and refreshed successfully."
    except ValueError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"❌ Error refreshing index: {str(e)}"


@mcp.tool(name="doxy_refresh")
async def doxy_refresh(project_path: Optional[str] = None) -> str:
    """Legacy wrapper for refresh_index."""
    return await refresh_index(project_path)


@mcp.tool()
async def get_symbol_at_location(
    file_path: str, line_number: int, project_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Find symbol at file/line position."""
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
        min_distance = float("inf")

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


@mcp.tool(name="doxy_at_loc")
async def doxy_at_loc(
    file_path: str, line_number: int, project_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Legacy wrapper for get_symbol_at_location."""
    return await get_symbol_at_location(file_path, line_number, project_path)


@mcp.tool()
async def query_active_symbol(project_path: Optional[str] = None) -> str:
    """Query docs for symbol at current cursor."""
    context = get_active_context()
    file_path = context.get("active_file")
    line_str = context.get("cursor_line")

    if not file_path or not line_str:
        return (
            "⚠️ No active file or cursor position detected in the environment. "
            "Ensure your MCP client provides 'MCP_ACTIVE_FILE' and 'MCP_CURSOR_LINE'."
        )

    try:
        line_number = int(line_str)
    except ValueError:
        return f"❌ Error: Invalid cursor line position: {line_str}"

    symbol = await get_symbol_at_location(file_path, line_number, project_path)

    if not symbol or (isinstance(symbol, dict) and "error" in symbol):
        return f"⚠️ No symbol found at {file_path}:{line_number}."

    return await query_project_reference(symbol["name"], project_path)


@mcp.tool(name="doxy_active")
async def doxy_active(project_path: Optional[str] = None) -> str:
    """Legacy wrapper for query_active_symbol."""
    return await query_active_symbol(project_path)


@mcp.tool()
async def get_file_structure(
    file_path: str, project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve all symbols defined in a file."""
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


@mcp.tool(name="doxy_file_struct")
async def doxy_file_struct(
    file_path: str, project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Legacy wrapper for get_file_structure."""
    return await get_file_structure(file_path, project_path)


async def _get_git_diff(cwd: Path) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "diff",
            "HEAD",
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace")
    except Exception:
        return ""


@mcp.tool()
async def generate_architecture_review(project_path: Optional[str] = None) -> str:
    """Generate visual HTML review of codebase architecture."""
    import tempfile
    import time

    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)
        if not xml_dir:
            return "❌ Error: Doxygen XML not found. Generate documentation first using 'doxy_generate'."

        from .reporter import generate_report_html

        # Run report generator in a thread
        html_content = await asyncio.to_thread(
            generate_report_html, resolved_path, xml_dir
        )

        # Write to temp file
        temp_dir = tempfile.gettempdir()
        filename = f"architecture-review-{int(time.time())}.html"
        file_path = os.path.join(temp_dir, filename)

        await asyncio.to_thread(
            lambda: Path(file_path).write_text(html_content, encoding="utf-8")
        )

        # Open in browser asynchronously
        def _open():
            try:
                import sys

                if sys.platform.startswith("linux"):
                    subprocess.Popen(
                        ["xdg-open", file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif sys.platform == "darwin":
                    subprocess.Popen(
                        ["open", file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif sys.platform == "win32":
                    os.startfile(file_path)
            except Exception as err:
                logger.warning("Could not open browser: %s", err)

        await asyncio.to_thread(_open)

        return f"✅ Architecture review generated at {file_path} and opened in browser."
    except Exception as e:
        return f"❌ Failed to generate architecture review: {str(e)}"


@mcp.tool()
async def generate_context_report(project_path: Optional[str] = None) -> str:
    """Generate deep token-efficient context report for LLM ingestion."""
    try:
        # pylint: disable=no-member
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)

        # Get primary language
        language = await asyncio.to_thread(detect_primary_language, resolved_path)

        # Get active git diff
        diff_text = await _get_git_diff(resolved_path)
        if diff_text:
            diff_text = diff_text[:5000]  # Limit size to avoid blowup
        else:
            diff_text = "No active changes."

        # Get project structure summary
        class_list, ns_list, file_list = [], [], []
        if xml_dir:
            engine = await DoxygenQueryEngine.create(xml_dir)
            class_list = engine.list_all_symbols(kind_filter="class")
            ns_list = engine.list_all_symbols(kind_filter="namespace")
            file_list = engine.list_all_symbols(kind_filter="file")

        # Build timeline summary of recent active files
        recent_changes = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "status",
                "--porcelain",
                cwd=str(resolved_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            status_lines = stdout.decode().splitlines()
            for line in status_lines[:10]:
                recent_changes.append(line.strip())
        except Exception:
            pass

        import datetime
        import hashlib

        from .reporter import get_git_version

        version = await asyncio.to_thread(get_git_version, resolved_path)
        date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        hasher = hashlib.sha256()
        hasher.update(f"{date_str}:{version}".encode("utf-8"))
        verification_hash = hasher.hexdigest()[:16]

        lines = [
            f"# Context Report: {resolved_path.name}",
            f"Project Path: {resolved_path}",
            f"Primary Language: {language}",
            f"Doxygen Index: {'Found' if xml_dir else 'Not found'}",
            f"Generated: {date_str}",
            f"Version: {version[:12]}",
            f"Verification Hash: {verification_hash}",
            "",
            "## Git Status",
            (
                "\n".join(recent_changes)
                if recent_changes
                else "No untracked or modified files."
            ),
            "",
            "## Structural Summary",
            f"Classes ({len(class_list)}): {', '.join(class_list[:15])}{'...' if len(class_list) > 15 else ''}",
            f"Namespaces ({len(ns_list)}): {', '.join(ns_list[:15])}{'...' if len(ns_list) > 15 else ''}",
            f"Files ({len(file_list)}): {', '.join(file_list[:15])}{'...' if len(file_list) > 15 else ''}",
            "",
            "## Git Diff (HEAD)",
            "```diff",
            diff_text,
            "```",
        ]

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to generate context report: {str(e)}"


@mcp.tool()
async def find_doc_gaps(project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scan codebase for undocumented symbols."""
    try:
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)
        language = await asyncio.to_thread(detect_primary_language, resolved_path)

        if language == "python":
            from .auditor import audit_python_files

            return await asyncio.to_thread(audit_python_files, resolved_path)

        xml_dir = await asyncio.to_thread(_find_xml_dir, resolved_path)
        if not xml_dir:
            return [{"error": "Doxygen XML not found. Generate documentation first."}]

        from .auditor import audit_doxygen_gaps

        engine = await DoxygenQueryEngine.create(xml_dir)
        return await asyncio.to_thread(audit_doxygen_gaps, engine, resolved_path)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool(name="doxy_doc_gaps")
async def doxy_doc_gaps(project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Legacy wrapper for find_doc_gaps."""
    return await find_doc_gaps(project_path)


@mcp.tool()
async def find_binary_gaps(project_path: Optional[str] = None) -> Dict[str, Any]:
    """Scan build objects for compiled symbol gaps."""
    try:
        resolved_path = await asyncio.to_thread(resolve_project_path, project_path)

        from .auditor import find_build_dir, find_nm_tool, scan_binary_gaps

        nm_tool = find_nm_tool()
        if not nm_tool:
            return {
                "error": "Binary dependency 'nm' or 'llvm-nm' not found in PATH.",
                "remediation": "Install binutils/llvm or configure DOXYGEN_NM_PATH environment variable.",
            }

        build_dir = find_build_dir(resolved_path)
        if not build_dir:
            return {
                "error": "Build directory not found.",
                "remediation": "Configure DOXYGEN_BUILD_DIR environment variable pointing to compiled object files.",
            }

        gaps = await asyncio.to_thread(scan_binary_gaps, nm_tool, build_dir)
        return {"nm_tool": nm_tool, "build_directory": str(build_dir), "gaps": gaps}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(name="doxy_binary_gaps")
async def doxy_binary_gaps(project_path: Optional[str] = None) -> Dict[str, Any]:
    """Legacy wrapper for find_binary_gaps."""
    return await find_binary_gaps(project_path)


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
                    "DOXYGEN_XML_DIR": "./docs/xml",
                },
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
    parser.add_argument(
        "--path", type=str, help="Target project path for configuration"
    )
    parser.add_argument("--vscode", action="store_true", help="Generate VS Code config")
    parser.add_argument(
        "--gemini", action="store_true", help="Generate Gemini CLI config"
    )
    parser.add_argument("--cursor", action="store_true", help="Generate Cursor config")

    args, _ = parser.parse_known_args()

    if args.version:
        pkg_v = "unknown"
        try:
            pkg_v = get_package_version("doxygen-mcp")
        except PackageNotFoundError:
            pass
        print(f"doxygen-mcp {pkg_v}")
        sys.exit(0)

    if args.command == "config":
        generate_config(args)
        sys.exit(0)

    # Check for Doxygen dependency
    doxygen_exe = get_doxygen_executable()
    try:
        subprocess.run(
            [doxygen_exe, "--version"], capture_output=True, check=True, shell=False
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning(
            "Doxygen not found at '%s'. Attempting automatic setup...", doxygen_exe
        )
        # Use existing check_environment script
        # src/doxygen_mcp/server.py -> src/doxygen_mcp -> src -> root
        script_path = (
            Path(__file__).parent.parent.parent / "scripts" / "check_environment.py"
        )
        if script_path.exists():
            try:
                subprocess.run(
                    [sys.executable, str(script_path), "--install"],
                    check=True,
                    shell=False,
                )
                # Re-verify after install
                subprocess.run(
                    [doxygen_exe, "--version"],
                    capture_output=True,
                    check=True,
                    shell=False,
                )
                logger.info("Doxygen successfully installed and verified.")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Automatic setup failed or Doxygen still not found: %s", e)
                logger.error(
                    "Please install Doxygen manually: https://www.doxygen.nl/download.html"
                )
                # We continue anyway to let MCP start, but tools will fail gracefully.
        else:
            logger.warning(
                "Setup script not found at %s. Skipping auto-setup.", script_path
            )

    # Only run MCP if not a custom command
    mcp.run()


if __name__ == "__main__":
    main()
