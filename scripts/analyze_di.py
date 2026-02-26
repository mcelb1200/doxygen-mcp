"""
Analyze Dependency Injection compliance using Doxygen XML data.
"""
# pylint: disable=duplicate-code
import os
import sys
from pathlib import Path

# Add src to path to import DoxygenQueryEngine
sys.path.append(str(Path("src").resolve()))
# pylint: disable=import-error, wrong-import-position
from doxygen_mcp.query_engine import DoxygenQueryEngine
# pylint: enable=import-error, wrong-import-position

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

def _check_class_di(class_name, engine):
    """Check a single class for DI compliance."""
    details = engine.query_symbol(class_name)
    if not details or "error" in details:
        return None

    members = details.get("members", [])

    # Find constructor
    constructors = [m for m in members if m["name"] == class_name]

    has_dependencies = False
    constructor_args = ""

    if constructors:
        for constructor in constructors:
            args = constructor["args"]
            constructor_args = args
            # Heuristic: Check for references (&) or pointers (*)
            if "&" in args or "*" in args:
                has_dependencies = True
                break

    # Check for singleton pattern (getInstance method)
    has_get_instance = any(m["name"] == "getInstance" for m in members)

    if not has_dependencies:
        reason = "No dependencies in constructor"
        if not constructors:
            if has_get_instance:
                reason = "Singleton (getInstance found, no public injection)"
            elif any(m.get("static") == "yes" for m in members):
                reason = "Static Utility Class (likely)"
            else:
                reason = "No Code Constructor / Implicit"

        return {
            "name": class_name,
            "reason": reason,
            "args": constructor_args,
            "has_get_instance": has_get_instance
        }
    return None

def analyze_di_compliance(xml_dir: str):
    """Analyze the project for DI compliance and print a report."""
    print("# Dependency Injection Compliance Report")
    print(f"\n**Analysis Target:** `{xml_dir}`")
    engine = DoxygenQueryEngine(xml_dir)

    # Get all classes
    classes = engine.list_all_symbols(kind_filter="class")
    print(f"\n- **Total Classes Found:** {len(classes)}")

    logic_classes = [c for c in classes if is_logic_class(c)]
    print(f"- **Logic Classes Analyzed:** {len(logic_classes)}")

    flagged_classes = []

    for class_name in logic_classes:
        flagged = _check_class_di(class_name, engine)
        if flagged:
            flagged_classes.append(flagged)

    print("\n## 🚨 Potential DI Violations")
    print("| Class Name | Reason | Singleton? |")
    print("| :--- | :--- | :---: |")

    suspicious_count = 0
    for flagged in sorted(flagged_classes, key=lambda x: x['name']):
        # Filter out some likely false positives or trivial classes if needed
        # For now, print all logic classes without clear dependencies
        if flagged["reason"] == "Static Utility Class (likely)":
            continue

        singleton_mark = "✅ Yes" if flagged['has_get_instance'] else "No"
        print(f"| `{flagged['name']}` | {flagged['reason']} | {singleton_mark} |")
        suspicious_count += 1

    print(
        f"\n**Summary:** Found **{suspicious_count}** suspicious classes "
        f"out of **{len(logic_classes)}** logic classes checked."
    )

if __name__ == "__main__":
    if "DOXYGEN_XML_DIR" not in os.environ:
        # Default to MidiKobold path if not set
        os.environ["DOXYGEN_XML_DIR"] = r"C:\GitHub\MidiKobold\xml"

    analyze_di_compliance(os.environ["DOXYGEN_XML_DIR"])
