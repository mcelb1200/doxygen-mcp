import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add src to python path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# pylint: disable=wrong-import-position,unused-argument
from doxygen_mcp.reporter import discover_candidates


class DummyEngine:
    """A simple dummy DoxygenQueryEngine designed to simulate heavily interconnected classes
    and force the O(N^2) loops in the original algorithm."""

    def __init__(self, num_classes=500, connections_per_class=10):
        self.classes = [f"Class{i}" for i in range(num_classes)]
        self._connections_per_class = connections_per_class

    def list_all_symbols(self, kind_filter):
        return self.classes

    def get_symbol_connections(self, cls):
        idx = int(cls.replace("Class", ""))

        # Each class references N other classes. Ensure there's coupling.
        refs = [
            f"Class{(idx + i) % len(self.classes)}"
            for i in range(1, self._connections_per_class + 1)
        ]

        # Add inheritance links
        base = [f"Class{(idx - 1) % len(self.classes)}"]
        derived = [f"Class{(idx + 1) % len(self.classes)}"]

        return {
            "members": [{"references": refs}],
            "base_classes": base,
            "derived_classes": derived,
        }

    def query_symbol(self, cls):
        return {"location": {"file": "dummy.py"}}


# pylint: disable=too-many-locals,too-many-branches,unused-argument,wrong-import-position
def original_discover_candidates(engine, _project_path: Path) -> List[Dict[str, Any]]:
    """The original unoptimized O(N^2) implementation."""
    candidates = []
    classes = engine.list_all_symbols(kind_filter="class")

    # 1. Look for Tightly Coupled Modules (cross-references)
    coupled_pairs = set()
    for cls in classes:
        conn = engine.get_symbol_connections(cls)
        if not conn or "error" in conn:
            continue
        referenced = set()
        for member in conn.get("members", []):
            referenced.update(member.get("references", []))

        for other in classes:
            if other == cls:
                continue
            if other in referenced:
                other_conn = engine.get_symbol_connections(other)
                if other_conn and "error" not in other_conn:
                    other_referenced = set()
                    for o_member in other_conn.get("members", []):
                        other_referenced.update(o_member.get("references", []))
                    if cls in other_referenced:
                        pair = tuple(sorted([cls, other]))
                        coupled_pairs.add(pair)

    for c1, c2 in list(coupled_pairs)[:3]:
        c1_details = engine.query_symbol(c1) or {}
        c2_details = engine.query_symbol(c2) or {}
        f1 = c1_details.get("location", {}).get("file", "unknown")
        f2 = c2_details.get("location", {}).get("file", "unknown")
        files = list(set([f1, f2]))

        mermaid_before = f"flowchart LR\n  {c1} <--> {c2}"
        mermaid_after = f"flowchart LR\n  subgraph Consolidated [Unified {c1}_{c2}]\n    {c1}\n    {c2}\n  end"

        candidates.append(
            {
                "title": f"Consolidate Coupled Classes {c1} and {c2}",
                "badge_strength": "Strong",
                "badge_category": "in-process",
                "files": files,
                "mermaid_before": mermaid_before,
                "mermaid_after": mermaid_after,
                "problem": f"Bi-directional coupling between class {c1} and {c2} violates clean module seams.",
                "solution": f"Merge {c1} and {c2} into a single unified module, hiding internal calls behind a clean seam.",
                "wins": [
                    "Locality: bugs concentrate in unified class",
                    "Leverage: single interface for callers",
                    "Delete redundant bridging methods",
                ],
            }
        )

    # 2. Look for Deep Class Inheritance
    for cls in classes:
        conn = engine.get_symbol_connections(cls)
        if not conn or "error" in conn:
            continue
        base_classes = conn.get("base_classes", [])
        derived_classes = conn.get("derived_classes", [])
        if base_classes and derived_classes:
            cls_details = engine.query_symbol(cls) or {}
            f = cls_details.get("location", {}).get("file", "unknown")

            mermaid_before = f"flowchart TD\n  {base_classes[0]} --> {cls}\n  {cls} --> {derived_classes[0]}"
            mermaid_after = f"flowchart TD\n  {derived_classes[0]} --> {base_classes[0]}\n  {derived_classes[0]} -.-> |composes| {cls}"

            candidates.append(
                {
                    "title": f"Flatten Deep Inheritance of {cls}",
                    "badge_strength": "Worth exploring",
                    "badge_category": "ports & adapters",
                    "files": [f],
                    "mermaid_before": mermaid_before,
                    "mermaid_after": mermaid_after,
                    "problem": f"Deep class hierarchy with {cls} introduces unnecessary complexity and high coupling.",
                    "solution": f"Flatten inheritance hierarchy, replacing middle layers with composition or direct interfaces.",
                    "wins": [
                        "Locality: simpler class hierarchy",
                        "Leverage: caller interacts with composite interface",
                        "Reduce base class dependency leakage",
                    ],
                }
            )
            if len(candidates) >= 3:
                break

    # 3. Default Fallback Candidate
    if not candidates:
        candidates.append(
            {
                "title": "Consolidate Doxygen MCP Config and Server Utilities",
                "badge_strength": "Worth exploring",
                "badge_category": "in-process",
                "files": ["src/doxygen_mcp/server.py", "src/doxygen_mcp/utils.py"],
            }
        )

    return candidates


def test_functional_parity_and_benchmark():
    # Use a moderately large number of classes to make the O(N^2) slow but not take forever
    num_classes = 1000
    engine = DummyEngine(num_classes=num_classes)
    project_path = Path(".")

    print(
        f"Benchmarking discover_candidates with {num_classes} highly connected classes..."
    )

    # Run original
    start_orig = time.perf_counter()
    candidates_orig = original_discover_candidates(engine, project_path)
    time_orig = time.perf_counter() - start_orig

    # Run optimized
    start_opt = time.perf_counter()
    candidates_opt = discover_candidates(engine, project_path)
    time_opt = time.perf_counter() - start_opt

    # We must sort or normalize candidates for comparison as sets can yield arbitrary order in Python
    # for the first 3 coupled pairs, though in this dummy engine it's deterministic.
    # To be safe, we'll verify length and a few properties.
    assert len(candidates_orig) == len(
        candidates_opt
    ), f"Candidate count mismatch: {len(candidates_orig)} vs {len(candidates_opt)}"

    titles_orig = {c["title"] for c in candidates_orig}
    titles_opt = {c["title"] for c in candidates_opt}
    assert (
        titles_orig == titles_opt
    ), "Functional parity failed: candidate titles do not match!"

    print("\nFunctional parity verified ✅")

    print(f"\nOriginal O(N^2) Implementation: {time_orig:.4f} seconds")
    print(f"Optimized O(N+E) Implementation: {time_opt:.4f} seconds")

    if time_orig > 0:
        improvement = (time_orig - time_opt) / time_orig * 100
        speedup = time_orig / time_opt
        print(f"Improvement: {improvement:.2f}% ({speedup:.1f}x faster)")


if __name__ == "__main__":
    test_functional_parity_and_benchmark()
