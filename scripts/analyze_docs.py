"""
Analyze documentation coverage using Doxygen XML.
"""

# pylint: disable=wrong-import-position,unused-import

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path to import DoxygenQueryEngine
sys.path.append(str(Path("src").resolve()))
from doxygen_mcp.query_engine import DoxygenQueryEngine

# Force UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def analyze_docs_coverage(xml_dir: str):
    """Scan XML for documentation coverage and identify gaps."""
    print("# Documentation Coverage Report")
    print(f"\n**Analysis Target:** `{xml_dir}`")

    engine = DoxygenQueryEngine(xml_dir)

    # Get all classes
    classes = engine.list_all_symbols(kind_filter="class")
    print(f"\n- **Total Classes Found:** {len(classes)}")

    documented = 0
    missing = []

    for class_info in classes:
        details = engine.query_symbol(class_info['name'])
        if details and (details.get('brief') or details.get('detailed')):
            documented += 1
        else:
            missing.append(class_info['name'])

    print(f"- **Documented Classes:** {documented}")
    print(f"- **Classes Missing Docs:** {len(missing)}")

    if missing:
        print("\n## Action Items: Missing Class Documentation")
        for m in missing[:15]:
            print(f"- [ ] `{m}`")

    # Functions coverage
    functions = engine.list_all_symbols(kind_filter="function")
    if functions:
        print(f"\n- **Total Functions Found:** {len(functions)}")
        # Partial scan of functions for performance
        gap_count = 0
        for f in functions[:50]:
            details = engine.query_symbol(f['name'])
            if not (details and (details.get('brief') or details.get('detailed'))):
                gap_count += 1
        print(f"- **Sampled Gaps:** Approx {gap_count * 2}% missing docs based on sample.")

if __name__ == "__main__":
    target = os.environ.get("DOXYGEN_XML_DIR", "docs/xml")
    if os.path.exists(target):
        analyze_docs_coverage(target)
    else:
        print(f"Error: XML directory not found at {target}")
