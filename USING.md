# Getting Started: Doxygen MCP

**Doxygen MCP** connects AI (Claude, Cursor, Gemini) to code docs. AI understands structure without reading all files. Faster, smarter.

---

## 🚀 Quick Start
### 1. Install Deps
Need `uv` and `doxygen`.

**Mac:** `brew install doxygen uv`
**Windows:** Doxygen [doxygen.nl](https://www.doxygen.nl/download.html), `uv` via astral.sh.

### 2. Config AI Client
Run in `doxygen-mcp` folder:

**Claude:** `uv run doxygen-mcp config` (copy JSON to config).
**Gemini:** `uv run doxygen-mcp config --gemini`

### 3. Restart
Restart client. Tools available.

---

## 📁 Other Projects
Default: current dir. Other project:

**Method A (Config Flag):**
`uv run doxygen-mcp config --path "/path/to/project"`

**Method B (Run Script):**
`./scripts/run.sh "/path/to/project"`

**Method C (Env Vars):**
Set `DOXYGEN_PROJECT_ROOT` & `DOXYGEN_ALLOWED_PATHS`.

### 🗜️ Token Compression, HTML Reviews, Surgical Refactoring & Audits
* **Token Crusher Middleware**: Output text is automatically compressed by default to save token costs. To bypass and receive raw outputs, set:
  `export DOXYGEN_COMPRESS_OUTPUT=false`
* **Visual Architecture Reviews**: Trigger `generate_architecture_review` to generate a local HTML report. It automatically opens in your web browser. Includes class structures, coupling, and Mermaid diagrams. Each report is timestamped and cryptographically verified.
* **Surgical Refactoring Tools**:
  * Run `doxy_references` to get a flat list of all call sites and occurrences (file, line, content) of any symbol across the codebase.
  * Run `doxy_rename_impact` to analyze the impact of renaming a symbol. Lists definitions, caller sites, and subclass/inheritance breakages.
  * Run `doxy_skeleton` to retrieve structural signatures of a file with all method/function bodies stripped.
  * Run `doxy_virtual_diff` to detect working tree signature modifications and contract breakages.
  * Run `doxy_trace_path` to trace call graphs sequentially starting from an entry symbol.
* **Incremental Delta Refresh**:
  * Run `doxy_refresh_delta` on a specific file or subdirectory to update its XML index incrementally in under a second, avoiding full index build latency.
* **Codebase & Documentation Audits**:
  * Run `doxy_doc_gaps` to identify public classes or functions lacking documentation (uses native Python AST parser for Python codebases).
  * Run `doxy_binary_gaps` to cross-reference build outputs (`.o` files via `nm`) with Doxygen headers to find stubs or compilation discrepancies. Configurable via `DOXYGEN_NM_PATH` and `DOXYGEN_BUILD_DIR`.
  * Run `doxy_parity_check` to detect documentation/signature parity mismatches (mismatched, redundant, or missing `@param` tags).

---

## 🤖 Usage (AI Questions)
Ask AI:
- "Project structure?"
- "Explain `UserAuthentication` class."
- "Functions in `server.py`?"
- "Generate docs for current file."

---

## 🛠️ Troubleshooting
**"Doxygen not found"**: Install Doxygen. Check `doxygen --version`.
**"No Doxyfile"**: Ask AI: *"Configure project for me"*. Runs `doxy_config`.
**"Symbol not found"**: Ask AI: *"Refresh index"*. Runs `doxy_refresh`.

---

## 🔄 Auto-Sync (Git Hooks)
Background Doxygen updates on commit/push.

### 1. Install
Run in project root:
`python path/to/scripts/install_hooks.py`

### 2. Result
- **Commit**: Fast incremental update on header change.
- **Push**: Full build (graphs/refs).
