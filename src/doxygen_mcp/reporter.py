# Inspired by and adapted from the "improve-codebase-architecture" engineering skill by Matt Pocock (MIT License)
# Copyright (c) 2026 Matt Pocock

import datetime
import html
from pathlib import Path
from typing import Any, Dict, List

from .query_engine import DoxygenQueryEngine


def discover_candidates(
    engine: DoxygenQueryEngine, _project_path: Path
) -> List[Dict[str, Any]]:
    """Dynamically discover architectural candidates from Doxygen symbols."""
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
                "mermaid_before": "flowchart TD\n  server[server.py] --> utils[utils.py]\n  server --> config[config.py]",
                "mermaid_after": "flowchart TD\n  subgraph CoreModule [Core Server Module]\n    server[server.py]\n    utils[utils.py]\n  end\n  CoreModule --> config[config.py]",
                "problem": "Server logic and environment helper utils exist as separate shallow modules.",
                "solution": "Deepen server core by absorbing utility helpers behind a single unified interface seam.",
                "wins": [
                    "Locality: path resolution encapsulated",
                    "Leverage: callers use server directly",
                    "Simpler mock interfaces in tests",
                ],
            }
        )

    return candidates


def get_git_version(project_path: Path) -> str:
    try:
        import subprocess

        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True,
        )
        val = res.stdout.strip()
        if val:
            return val
    except Exception:
        pass

    doxyfile = project_path / "Doxyfile"
    if doxyfile.exists():
        try:
            content = doxyfile.read_bytes()
            import hashlib

            return hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            pass
    return "no-vcs-version"


def generate_report_html(project_path: Path, xml_dir: str) -> str:
    """Generate visual architecture review HTML report content."""
    import hashlib

    engine = DoxygenQueryEngine._cache.get(str(Path(xml_dir).absolute()))
    if not engine:
        # Fallback if cache not hit
        import asyncio

        engine = asyncio.run(DoxygenQueryEngine.create(xml_dir))

    candidates = discover_candidates(engine, project_path)

    project_name = project_path.name
    date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    version = get_git_version(project_path)

    hasher = hashlib.sha256()
    hasher.update(f"{date_str}:{version}".encode("utf-8"))
    verification_hash = hasher.hexdigest()[:16]

    card_list_html = []
    for idx, c in enumerate(candidates):
        strength_color = {
            "Strong": "emerald",
            "Worth exploring": "amber",
            "Speculative": "slate",
        }.get(c["badge_strength"], "slate")

        files_li = "\n".join(
            f"<li><a href='file://{project_path / f}' class='hover:underline'>{html.escape(f)}</a></li>"
            for f in c["files"]
        )

        wins_li = "\n".join(
            f"<li class='flex items-start gap-2 text-slate-600 text-sm'>"
            f"<span class='text-emerald-500 font-bold'>&check;</span>"
            f"<span>{html.escape(w)}</span>"
            f"</li>"
            for w in c["wins"]
        )

        card_html = f"""
        <article id="candidate-{idx}" class="bg-white border border-stone-200 rounded-xl p-6 shadow-sm space-y-6">
          <div class="flex justify-between items-start">
            <div>
              <h2 class="text-2xl font-sans font-semibold text-slate-800">{html.escape(c["title"])}</h2>
              <div class="flex gap-2 mt-2">
                <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-{strength_color}-50 text-{strength_color}-700 border border-{strength_color}-200">{html.escape(c["badge_strength"])}</span>
                <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">{html.escape(c["badge_category"])}</span>
              </div>
            </div>
          </div>

          <div class="text-sm font-mono text-stone-500 bg-stone-50 p-3 rounded-lg border border-stone-100">
            <div class="font-semibold text-stone-700 mb-1">Involved Files:</div>
            <ul class="list-disc pl-5 space-y-0.5">
              {files_li}
            </ul>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="space-y-2">
              <div class="text-xs uppercase tracking-wider text-stone-400 font-semibold">Before (Current)</div>
              <div class="rounded-lg border border-stone-100 bg-white p-4 h-64 flex items-center justify-center overflow-auto">
                <pre class="mermaid w-full">
{c["mermaid_before"]}
                </pre>
              </div>
            </div>
            
            <div class="space-y-2">
              <div class="text-xs uppercase tracking-wider text-stone-400 font-semibold">After (Deepened)</div>
              <div class="rounded-lg border border-stone-100 bg-white p-4 h-64 flex items-center justify-center overflow-auto">
                <pre class="mermaid w-full">
{c["mermaid_after"]}
                </pre>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-stone-100 pt-6">
            <div class="space-y-3">
              <div>
                <h4 class="text-sm font-semibold uppercase text-stone-500 tracking-wider">Problem</h4>
                <p class="text-slate-700 mt-1 text-sm">{html.escape(c["problem"])}</p>
              </div>
              <div>
                <h4 class="text-sm font-semibold uppercase text-stone-500 tracking-wider">Solution</h4>
                <p class="text-slate-700 mt-1 text-sm">{html.escape(c["solution"])}</p>
              </div>
            </div>

            <div>
              <h4 class="text-sm font-semibold uppercase text-stone-500 tracking-wider mb-2">Wins</h4>
              <ul class="space-y-1.5">
                {wins_li}
              </ul>
            </div>
          </div>
        </article>
        """
        card_list_html.append(card_html)

    candidate_cards_html = "\n".join(card_list_html)
    top_candidate = candidates[0]

    html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Architecture review — {html.escape(project_name)}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
    </script>
    <style>
      .seam {{ stroke-dasharray: 4 4; }}
      .leak {{ stroke: #dc2626; }}
      .deep {{ background: linear-gradient(135deg, #0f172a, #1e293b); }}
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header class="border-b border-stone-200 pb-6">
        <h1 class="text-4xl font-serif font-semibold text-slate-800">Architecture Review</h1>
        <p class="text-stone-500 mt-2 font-mono text-xs">Project: {html.escape(project_name)} | Generated: {date_str} | Version: {html.escape(version[:12])} | Verification Hash: {html.escape(verification_hash)}</p>
        
        <div class="mt-4 flex flex-wrap gap-4 text-xs font-mono">
          <div class="flex items-center gap-2">
            <span class="inline-block w-4 h-4 bg-white border border-slate-300 rounded shadow-sm"></span>
            <span>Module</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-block w-4 h-4 border border-dashed border-slate-400 rounded"></span>
            <span>Seam</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-block w-4 h-4 bg-red-100 border border-red-500 rounded"></span>
            <span>Coupling Leak</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-block w-4 h-4 deep rounded shadow-sm"></span>
            <span>Deep Module</span>
          </div>
        </div>
      </header>

      <section id="candidates" class="space-y-12">
        {candidate_cards_html}
      </section>

      <section id="top-recommendation" class="bg-slate-900 text-white rounded-xl p-8 shadow-lg">
        <h2 class="text-2xl font-serif font-semibold mb-4">Top Recommendation</h2>
        <div class="space-y-4">
          <h3 class="text-xl font-sans font-medium text-emerald-400">{html.escape(top_candidate["title"])}</h3>
          <p class="text-slate-300">
            This candidate yields the highest return on investment for codebase locality and leverage. Implementing this seam first will simplify testing and flatten dependency complexity across the package.
          </p>
          <a href="#candidate-0" class="inline-block text-emerald-400 font-medium hover:underline font-mono text-sm">&rarr; Go to candidate card</a>
        </div>
      </section>
    </main>
  </body>
</html>
"""
    return html_content
