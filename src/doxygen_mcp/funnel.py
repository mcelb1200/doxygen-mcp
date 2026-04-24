"""
High-Resolution Context Funnel for Doxygen XML.
Standardizes minification and repository onboarding for AI context.
"""
import os
import sys
import xml.etree.ElementTree as ET
import glob
import argparse
from pathlib import Path

def minify_xml_file(filepath):
    """Minifies a Doxygen XML file while preserving AI-critical metadata."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        changed = False

        # Tags to completely remove (graphs and redundant lists)
        tags_to_remove = [
            'collaborationgraph',
            'inheritancegraph',
            'listofallmembers',
            'incdepgraph',
            'invincdepgraph',
            'directorygraph'
        ]

        # Remove heavy/low-signal nodes
        for tag in tags_to_remove:
            for parent in root.findall(f".//{tag}/.."):
                for elem in parent.findall(tag):
                    parent.remove(elem)
                    changed = True

        # Strip empty detaileddescription or briefdescription
        for desc_tag in ['briefdescription', 'detaileddescription']:
            for parent in root.findall(f".//{desc_tag}/.."):
                for elem in parent.findall(desc_tag):
                    if len(elem) == 0 and (elem.text is None or elem.text.strip() == ""):
                        parent.remove(elem)
                        changed = True

        # Minify text (collapse whitespace) to save tokens
        for elem in root.iter():
            if elem.text and not elem.text.strip():
                elem.text = ""
            if elem.tail and not elem.tail.strip():
                elem.tail = ""

        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        return True
            
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def filter_main():
    """CLI entry point for the SNR filter."""
    parser = argparse.ArgumentParser(description='Doxygen XML SNR Filter')
    parser.add_argument('xml_dir', nargs='?', default='docs/xml', help='Directory containing Doxygen XML files')
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

def setup_funnel(repo_path: str):
    """Installs Doxyfile.fast and post-commit hook into a repository."""
    repo = Path(repo_path).resolve()
    if not (repo / ".git").exists():
        return False, f"Not a git repository: {repo}"

    # 1. Ensure a base Doxyfile exists
    base_doxyfile = repo / "Doxyfile"
    if not base_doxyfile.exists():
        print(f"⚠️  Base Doxyfile not found in {repo.name}. Generating a default one...")
        import subprocess
        try:
            subprocess.run(["doxygen", "-g", str(base_doxyfile)], check=True, capture_output=True)
        except Exception as e:
            return False, f"Failed to generate base Doxyfile: {e}"

    # 2. Create Doxyfile.fast
    doxy_fast = repo / "Doxyfile.fast"
    if doxy_fast.exists():
        print(f"ℹ️  Doxyfile.fast already exists in {repo.name}. Overwriting with standard AI-Context overrides...")

    doxyfile_content = """# Doxyfile.fast - Optimized for AI Context
@INCLUDE               = Doxyfile
GENERATE_HTML          = NO
GENERATE_LATEX         = NO
GENERATE_XML           = YES
XML_OUTPUT             = docs/xml
RECURSIVE              = YES
REFERENCES_RELATION    = YES
REFERENCED_BY_RELATION = YES
HAVE_DOT               = NO
CALL_GRAPH             = NO
CALLER_GRAPH           = NO
INCLUDE_GRAPH          = NO
INCLUDED_BY_GRAPH      = NO
"""
    with open(doxy_fast, "w") as f:
        f.write(doxyfile_content)

    # 2. Install post-commit hook
    hook_dir = repo / ".git" / "hooks"
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
    with open(hook_path, "w") as f:
        f.write(hook_content)
    
    os.chmod(hook_path, 0o755)
    return True, f"Successfully configured context funnel for {repo.name}"

def setup_main():
    """CLI entry point for the setup utility."""
    parser = argparse.ArgumentParser(description='Doxygen Context Funnel Setup')
    parser.add_argument('repo_path', nargs='?', default='.', help='Path to the repository root')
    args = parser.parse_args()
    
    success, msg = setup_funnel(args.repo_path)
    print(msg)
    sys.exit(0 if success else 1)
