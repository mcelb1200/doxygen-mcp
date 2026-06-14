"""
High-Resolution Context Funnel for Doxygen XML.
Standardizes minification and repository onboarding for AI context.
"""

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

import defusedxml.ElementTree as ET


def minify_xml_file(filepath):
    """Minifies a Doxygen XML file while preserving AI-critical metadata."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        if root is None:
            return False

        # Tags to completely remove (graphs and redundant lists)
        tags_to_remove = [
            "collaborationgraph",
            "inheritancegraph",
            "listofallmembers",
            "incdepgraph",
            "invincdepgraph",
            "directorygraph",
        ]

        # Remove heavy/low-signal nodes
        for tag in tags_to_remove:
            for parent in root.findall(f".//{tag}/.."):
                if parent is not None:
                    for elem in parent.findall(tag):
                        parent.remove(elem)

        # Strip empty detaileddescription or briefdescription
        for desc_tag in ["briefdescription", "detaileddescription"]:
            for parent in root.findall(f".//{desc_tag}/.."):
                if parent is not None:
                    for elem in parent.findall(desc_tag):
                        if elem is not None:
                            if len(elem) == 0 and (
                                elem.text is None or elem.text.strip() == ""
                            ):
                                parent.remove(elem)

        # Minify text (collapse whitespace) to save tokens
        for elem in root.iter():
            if elem is not None:
                if elem.text and not elem.text.strip():
                    elem.text = ""
                if elem.tail and not elem.tail.strip():
                    elem.tail = ""

        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        return True

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def filter_main():
    """CLI entry point for the SNR filter."""
    parser = argparse.ArgumentParser(description="Doxygen XML SNR Filter")
    parser.add_argument(
        "xml_dir",
        nargs="?",
        default="docs/xml",
        help="Directory containing Doxygen XML files",
    )
    args = parser.parse_args()

    if not os.path.exists(args.xml_dir):
        print(f"Directory {args.xml_dir} not found.")
        sys.exit(1)

    xml_files = glob.glob(os.path.join(args.xml_dir, "*.xml"))
    processed = 0
    for f in xml_files:
        if minify_xml_file(f):
            processed += 1

    print(f"Minified {processed}/{len(xml_files)} XML files in {args.xml_dir}")


def get_git_hooks_dir(repo: Path) -> Path:
    """Resolve the correct git hooks directory path (worktree-aware)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        p = Path(result.stdout.strip())
        if not p.is_absolute():
            p = (repo / p).resolve()
        return p
    except Exception:
        # Fallback to standard .git/hooks directory
        return repo / ".git" / "hooks"


def setup_funnel(repo_path: str):
    """Installs Doxyfile.fast and post-commit hook into a repository."""
    repo = Path(repo_path).resolve()
    # Check if git repository in a worktree-aware way
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"], cwd=repo, capture_output=True, check=True
        )
    except Exception:
        return False, f"Not a git repository: {repo}"

    # 1. Ensure a base Doxyfile exists
    base_doxyfile = repo / "Doxyfile"
    if not base_doxyfile.exists():
        print(
            f"[WARNING] Base Doxyfile not found in {repo.name}. Generating a default one..."
        )
        try:
            subprocess.run(
                ["doxygen", "-g", str(base_doxyfile)], check=True, capture_output=True
            )
        except Exception as e:
            return False, f"Failed to generate base Doxyfile: {e}"

    # 2. Create Doxyfile.fast
    doxy_fast = repo / "Doxyfile.fast"
    if doxy_fast.exists():
        print(
            f"[INFO] Doxyfile.fast already exists in {repo.name}. Preserving existing configuration."
        )
    else:
        doxyfile_content = """# Doxyfile.fast - Optimized for AI Context (Lightning Fast)
@INCLUDE               = Doxyfile
GENERATE_HTML          = NO
GENERATE_LATEX         = NO
GENERATE_XML           = YES
XML_OUTPUT             = docs/xml
RECURSIVE              = YES
REFERENCES_RELATION    = YES
REFERENCED_BY_RELATION = YES
HAVE_DOT               = NO
CLASS_GRAPH            = NO
COLLABORATION_GRAPH    = NO
CALL_GRAPH             = NO
CALLER_GRAPH           = NO
INCLUDE_GRAPH          = NO
INCLUDED_BY_GRAPH      = NO

# Silence diagnostic noise but capture to log for enrichment
QUIET                  = YES
WARNINGS               = YES
WARN_IF_UNDOCUMENTED   = YES
WARN_IF_DOC_ERROR      = YES
WARN_FORMAT            = "$file:$line: $text"
WARN_LOGFILE           = logs/doxygen_warnings.log

VERBATIM_HEADERS       = NO
SOURCE_BROWSER         = NO
INLINE_SOURCES         = NO
"""
        with open(doxy_fast, "w", encoding="utf-8") as f:
            f.write(doxyfile_content)

    # 2. Install post-commit hook
    hook_dir = get_git_hooks_dir(repo)
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hook_dir / "post-commit"

    # Resolve absolute path to the filter binary
    filter_bin = Path(sys.executable).parent / "doxygen-snr-filter"

    hook_content = f"""#!/bin/bash
# Doxygen Context Funnel Hook
# Automatically triggered by doxygen-mcp

changed_files=$(git diff-tree -r --name-only HEAD)
if echo "$changed_files" | grep -E "\\.(h|hpp|cpp|c|py|ts|tsx)$" > /dev/null; then
    echo "Documentation Hook: Updating AI Context index..."
    (
        cd "$(git rev-parse --show-toplevel)" || exit
        doxygen Doxyfile.fast > /dev/null 2>&1
        {filter_bin} docs/xml > /dev/null 2>&1
    ) &
fi
"""
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(hook_content)

    os.chmod(hook_path, 0o755)
    return True, f"Successfully configured context funnel for {repo.name}"


def setup_main():
    """CLI entry point for the setup utility."""
    parser = argparse.ArgumentParser(description="Doxygen Context Funnel Setup")
    parser.add_argument(
        "repo_path", nargs="?", default=".", help="Path to the repository root"
    )
    args = parser.parse_args()

    success, msg = setup_funnel(args.repo_path)
    print(msg)
    sys.exit(0 if success else 1)
