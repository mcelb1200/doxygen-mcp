---
name: doxygen-investigation
description: >
  Guide for AI agents to perform token-efficient, high-precision codebase navigation
  and dependency mapping using Doxygen MCP tools. Use this skill when investigating
  namespaces, classes, call paths, signature deltas, and code architecture.
---

# Codebase Investigation via Doxygen MCP

Use this skill when navigating an unfamiliar codebase, refactoring APIs, tracing call paths, or locating code components without reading raw files.

## Guidelines for Token Efficiency

To minimize token cost and prevent context window exhaustion, prioritize structural information over raw source code:

1. **Avoid Reading Full Files**:
   - Use `doxy_skeleton` to retrieve the outline of classes, methods, and signatures (with bodies replaced by stubs).
   - Use `doxy_query` to inspect a specific symbol's interface, relations, and docstrings.
   - Do NOT use `read_file` unless you are actively preparing to edit the code.

2. **Map Architecture First**:
   - Start with `generate_context_report` to orient the session (identifies languages, git status, and structural metrics).
   - Run `doxy_structure` to inspect the namespace and class inheritance trees.

3. **Trace Execution Graphically**:
   - Use `doxy_trace_path` to trace call sequences chronologically across files rather than manually reading multiple classes.
   - Use `doxy_references` to locate call sites instead of performing global grep searches.

## Determinative Decision Matrix

Use the matrix below to select the most efficient tool for your task:

| Goal / Scenario | Recommended Tool | Rationale |
| :--- | :--- | :--- |
| **Inspect file signatures** | `doxy_skeleton` | Excludes function bodies, saving up to 90% of tokens compared to reading the raw file. |
| **Find symbol usage** | `doxy_references` | Returns exact file & line matches for call sites, avoiding fuzzy text search noise. |
| **Understand symbol contract** | `doxy_query` | Shows docstrings, signatures, and hierarchy relations directly. |
| **Check refactor impact** | `doxy_rename_impact` | Traces subclass trees and callers to identify where contract breakages will occur. |
| **Verify active edits** | `doxy_virtual_diff` | Instantly lists signature changes in the working tree compared to the indexed baseline. |
| **Update stale index** | `doxy_refresh_delta` | Syncs index for the modified file in < 1 second instead of doing a full index build. |

## Project Setup & Configuration

- **doxygen_mcp.json**: Create in project root to configure neighbor project accesses (`allowed_paths`) and custom XML folders (`xml_dir`). Supports `~` and env variable expansion (e.g. `~/github/dependency`).
- **Dynamic CWD Resolution**: The global MCP server dynamically discovers project context using workspace CWD when env variables are omitted.
