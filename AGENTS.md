# AI Agent Guide (Code Investigation)

Guide for AI agents (Jules, Gemini, Claude). Use `doxygen-mcp` investigate codebase. Max context, min tokens.

## 🎯 Objective
Deep understanding architecture, dependencies, symbols. No raw file read.

## 🛠️ Core Tools & Workflow

### 1. Recon (Low Tokens)
No `list_files`. Start with deep context tool:

*   **`generate_context_report`**:
    *   **Purpose**: Get repository overview, primary language, active git diff, structural stats, and index existence in a single call. Includes timestamped integrity verification hash.
    *   **Use**: Instantly orient session. Highly compressed.

*   **`doxy_context`**:
    *   **Purpose**: Identify root, language, Doxygen config.
    *   **Use**: Legacy fallback.

*   **`doxy_scan`**:
    *   **Purpose**: File types and counts.
    *   **Use**: Know scale, languages.

### 2. Map Architecture (Mid Tokens)
Map structure:

*   **`doxy_structure`**:
    *   **Purpose**: Tree of namespaces, classes, files.
    *   **Use**: High-level architecture, find logic.
    *   **Tip**: Better than `list_files`.

### 3. Deep Symbol Dive (Targeted)
Understand component:

*   **`doxy_query`**:
    *   **Purpose**: Symbol docs (signatures, descriptions, relations).
    *   **Arg**: `symbol_name` (e.g., `MyClass`, `processData`).
    *   **Use**: Unknown class/function contract.
    *   **Win**: Relevant info + inheritance. No implementation noise.

*   **`doxy_file_struct`**:
    *   **Purpose**: List symbols in file.
    *   **Arg**: `file_path`.
    *   **Use**: Before edit, verify contents without raw read.

### 4. IDE Assist
IDE (VS Code, Cursor):

*   **`doxy_active`**:
    *   **Purpose**: Document symbol at cursor.
    *   **Use**: "What this do?" or "Explain code".

### 5. Surgical Refactoring Tools
*   **`doxy_references`**:
    *   **Purpose**: Find all call sites / occurrences of a symbol with precise file and line number.
    *   **Use**: Before renaming or modifying, find all dependencies to change.
*   **`doxy_rename_impact`**:
    *   **Purpose**: Predict renaming impact on codebase.
    *   **Use**: Pre-refactor analysis to list definition sites, callers, and subclass hierarchy changes.
*   **`doxy_skeleton`**:
    *   **Purpose**: Strip function/method bodies, returning a pure structural skeleton to save tokens.
    *   **Use**: Get high-level file signature structure without reading full implementations.
*   **`doxy_virtual_diff`**:
    *   **Purpose**: Predict contract breakage by diffing working tree signatures against the Doxygen index.
    *   **Use**: Identify active refactoring deltas and potential API breakages.
*   **`doxy_trace_path`**:
    *   **Purpose**: Chain call path code snippets sequentially to target execution path debugging.
    *   **Use**: Compile direct call pipeline contexts without full file overhead.
*   **`doxy_refresh_delta`**:
    *   **Purpose**: Lightweight incremental scan of modified file or subdir.
    *   **Use**: Instantly update semantic graph for edited file without full index build latency.
*   **`doxy_parity_check`**:
    *   **Purpose**: Scan codebase for parameter comment vs function signature mismatches.
    *   **Use**: Validate `@param` tags (mismatched, redundant, or missing).

### 6. Gap Audits
Auditing codebase state and stubs:

*   **`doxy_doc_gaps`**:
    *   **Purpose**: Identify undocumented public classes and functions (uses native Python AST parser for Python codebases).
    *   **Use**: Quickly find missing docs.

*   **`doxy_binary_gaps`**:
    *   **Purpose**: Identify compiled symbol stubs by matching compiler undefined references with headers.
    *   **Use**: Check for missing implementation parts.

## 💡 Best Practices (Token Save)

### 📊 Refactoring & Debugging Tool Selection Matrix

| Scenario / Goal | Recommended Tool | Rationale & Token Saving |
| :--- | :--- | :--- |
| **Mechanical Refactoring** (e.g. Renaming variables/methods) | `doxy_references` | Returns a flat list of precise file + line matches instead of parsing full file contents. |
| **Rename Impact Assessment** (e.g. Renaming APIs or classes) | `doxy_rename_impact` | Traces callers, definition sites, and subclass hierarchy to pinpoint contract breakages. |
| **Verification of Active Edits** (Working tree vs Index) | `doxy_virtual_diff` | Instantly lists signature changes (added/removed/modified) without re-running full indexing. |
| **Structural File Inspection** (Class/methods overview) | `doxy_skeleton` | Returns class/function signatures with method bodies replaced with `pass` / `/* stub */`, saving massive token context. |
| **Debugging Stack Traces / Flows** (Chronological tracing) | `doxy_trace_path` | Recursively walks the call graph from an entry point and chains relevant code snippets sequentially. |
| **State Out of Date Mid-Refactor** (Update index for file) | `doxy_refresh_delta` | Incrementally refreshes the XML index for a single file or directory in under a second. |
| **Code Review / Compliance** (Parameter tags alignment) | `doxy_parity_check` | Audits `@param` documentation against the actual function arguments to find mismatches. |

1.  **Use `generate_context_report` first**:
    *   Retrieves project status, language, git diff, and structures in a single call, avoiding multiple tool executions.
 
2.  **`doxy_skeleton` > `read_file`**:
    *   Reading the full file wastes tokens on method bodies. Use `doxy_skeleton` to read only signatures first.

3.  **`doxy_query` > `read_file`**:
    *   Raw file = too many tokens.
    *   Query symbol = interface + docs. Enough.
 
4.  **`doxy_structure` to navigate**:
    *   No path guess. Use map find file.
 
5.  **Automatic Output Compression (Token Crusher)**:
    *   MCP server outputs are automatically compressed in caveman style (fluff stripped, synonyms used) to save context tokens. No agent action needed.
 
6.  **Check `doxygen_status`**:
    *   If Doxygen index not found, run `doxy_config` and `doxy_generate` first.

## ⚙️ Project Configuration & Discovery

1. **CWD Auto-Discovery**:
   - The global `doxygen-mcp` server resolves the project root dynamically from the active client CWD (workspace directory) when no env variables are specified.
2. **Project Configuration (`doxygen_mcp.json`)**:
   - Create `doxygen_mcp.json` in project root to authorize extra paths (`allowed_paths`) and set custom Doxygen XML folders (`xml_dir`).
   - Configuration paths support `~` and env variable expansion (e.g. `~/github/dependency-repo`).
3. **Git Worktree Support**:
   - Fully aware of Git worktrees. Resolves git hook installation paths using `git rev-parse --git-path hooks` (resolves to `.git/common/hooks` inside worktrees).
   - Resolves repository root path using `git rev-parse --show-toplevel` or fallback checks.

## 🔄 Example Workflow

**User**: "How auth work?"

**Bad Approach**:
1.  `list_files` (heavy)
2.  `read_file auth.py` (heavy)
3.  `read_file user.py` (heavy)

**Good Approach (Investigator)**:
1.  `doxy_structure` -> Find `AuthManager` + `auth/`.
2.  `doxy_query(symbol_name="AuthManager")` -> Methods (`login`, `logout`, `verify`).
3.  `doxy_file_struct(file_path="src/auth/utils.py")` -> Helpers.
4.  Need details? `read_file(...)`.

## 📡 Reporting Standards (Inter-Agent)
Use **Hybrid Narrative Compression (Caveman)** for all reports sent to other agents:
- **Technical Terms EXACT**: Keep symbol names, types, and JSON keys raw.
- **Narrative Stripping**: Remove articles/filler from descriptions.
- **Goal**: Maximize SNR, minimize token cost.
