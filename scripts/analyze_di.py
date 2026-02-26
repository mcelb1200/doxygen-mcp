"""
Analyze Dependency Injection compliance using Doxygen XML data.
"""
# pylint: disable=import-error, wrong-import-position
import os
import sys
from pathlib import Path

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

def _get_flagged_reason(class_name, members, has_dependencies):
    """Determine the reason a class might be flagged for DI violation."""
    if has_dependencies:
        return None

    constructors = [m for m in members if m["name"] == class_name]
    has_get_instance = any(m["name"] == "getInstance" for m in members)

    if not constructors:
        if has_get_instance:
            return "Singleton (getInstance found, no public injection)"
        if any(m.get("static") == "yes" for m in members):
            return "Static Utility Class (likely)"
        return "No Code Constructor / Implicit"

    return "No dependencies in constructor"

def analyze_di_compliance(xml_dir: str):
    """Analyze the project for DI compliance and print a report."""
    print("# Dependency Injection Compliance Report")
    print(f"\n**Analysis Target:** `{xml_dir}`")
    engine = DoxygenQueryEngine(xml_dir)

    classes = engine.list_all_symbols(kind_filter="class")
    print(f"\n- **Total Classes Found:** {len(classes)}")

    logic_classes = [c for c in classes if is_logic_class(c)]
    print(f"- **Logic Classes Analyzed:** {len(logic_classes)}")

    flagged_classes = []
    for class_name in logic_classes:
        details = engine.query_symbol(class_name)
        if not details or "error" in details:
            continue

        members = details.get("members", [])
        constructors = [m for m in members if m["name"] == class_name]

        has_dependencies = False
        constructor_args = ""
        for c in constructors:
            args = c.get("args", "")
            constructor_args = args
            if "&" in args or "*" in args:
                has_dependencies = True
                break

        reason = _get_flagged_reason(class_name, members, has_dependencies)
        if reason:
            flagged_classes.append({
                "name": class_name,
                "reason": reason,
                "args": constructor_args,
                "has_get_instance": any(m["name"] == "getInstance" for m in members)
            })

    print("\n## 🚨 Potential DI Violations")
    print("| Class Name | Reason | Singleton? |")
    print("| :--- | :--- | :---: |")

    suspicious_count = 0
    for c in sorted(flagged_classes, key=lambda x: x['name']):
        if c["reason"] == "Static Utility Class (likely)":
            continue
        singleton_mark = "✅ Yes" if c['has_get_instance'] else "No"
        print(f"| `{c['name']}` | {c['reason']} | {singleton_mark} |")
        suspicious_count += 1

    print(f"\n**Summary:** Found **{suspicious_count}** suspicious classes.")

if __name__ == "__main__":
    target_dir = os.environ.get("DOXYGEN_XML_DIR", r"C:\GitHub\MidiKobold\xml")
    analyze_di_compliance(target_dir)
