"""
Analyze Dependency Injection patterns in the codebase using Doxygen XML.
"""

# pylint: disable=wrong-import-position,too-many-locals,unused-import

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path to import DoxygenQueryEngine
sys.path.append(str(Path("src").resolve()))
from doxygen_mcp.query_engine import DoxygenQueryEngine

# Force UTF-8 output for Windows console redirection
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def is_logic_class(name: str) -> bool:
    """Check if class name suggests it contains business logic."""
    suffixes = [
        "Manager", "Controller", "Processor", "Engine",
        "Service", "Provider", "View", "Strategy"
    ]
    return any(name.endswith(s) for s in suffixes)

def analyze_di_patterns(xml_dir: str):
    """Scan XML for potential dependency injection compliance and violations."""
    print("# Dependency Injection Compliance Report")
    print(f"\n**Analysis Target:** `{xml_dir}`")

    engine = DoxygenQueryEngine(xml_dir)

    # Get all classes
    classes = engine.list_all_symbols(kind_filter="class")
    print(f"\n- **Total Classes Found:** {len(classes)}")

    logic_classes = [c for c in classes if is_logic_class(c['name'])]
    print(f"- **Classes requiring DI (heuristic):** {len(logic_classes)}")

    violations = []
    compliance = []

    for class_info in logic_classes:
        details = engine.query_symbol(class_info['name'])
        if not details: continue

        has_constructor = False
        constructor_params = []
        global_vars_used = False

        for member in details.get('members', []):
            if member['kind'] == 'function' and member['name'] == class_info['name'].split('::')[-1]:
                has_constructor = True
                constructor_params.append(member.get('argsstring', ''))

            # Check for direct global access in detailed description (crude heuristic)
            if 'detailed' in details and 'global' in details['detailed'].lower():
                global_vars_used = True

        if has_constructor and any(constructor_params):
            compliance.append(class_info['name'])
        else:
            violations.append(class_info['name'])

    print(f"\n## Compliance Summary")
    print(f"- ✅ **Compliant classes:** {len(compliance)}")
    print(f"- ⚠️ **Potential Violations:** {len(violations)}")

    if violations:
        print("\n### Details: Potential Violations")
        for v in violations[:10]:
            print(f"- `{v}`: Missing constructor-based injection or uses static patterns.")

    if len(logic_classes) > 0:
        score = (len(compliance) / len(logic_classes)) * 100
        print(f"\n**Overall DI Score:** {score:.1f}%")

if __name__ == "__main__":
    target = os.environ.get("DOXYGEN_XML_DIR", "docs/xml")
    if os.path.exists(target):
        analyze_di_patterns(target)
    else:
        print(f"Error: XML directory not found at {target}")
