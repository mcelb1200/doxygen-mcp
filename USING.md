# Getting Started: Doxygen MCP

**Doxygen MCP** connects AI (Claude, Cursor, Gemini) to code docs. AI understands structure without reading all files. Faster, smarter.

---

## 🚀 Quick Start
### 1. Install Deps
Need `uv` and `doxygen`.

**Mac:** `brew install doxygen uv`
**Windows:** Doxygen [doxygen.nl](https://www.doxygen.nl/download.html), `uv` via astral.sh.

### 2. Run Setup Script (Recommended)
Run `./scripts/setup.sh [/optional/target/project/path]` to automatically configure dependencies and generate the client configuration JSON.

### 3. Config AI Client
If setup script wasn't used with path, run in `doxygen-mcp` folder:

**Claude:** `uv run doxygen-mcp config` (copy JSON to config).
**Gemini:** `uv run doxygen-mcp config --gemini`

### 4. Restart
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

### 📁 Project-level Allowed Paths (doxygen_mcp.json)
To allow a single global server instance to safely access other projects or dependencies, create a `doxygen_mcp.json` file in your project's root folder:
```json
{
  "allowed_paths": [
    "/absolute/path/to/other/project",
    "../relative-neighbor-project"
  ]
}
```

## ⚙️ Advanced Features

### 🗜️ Token Crusher Middleware
Output text is automatically compressed using Caveman SNR rules by default to save LLM token costs.
- **Bypass**: To receive raw outputs, set `export DOXYGEN_COMPRESS_OUTPUT=false`.

### 📦 Structured Output Model
All tool outputs are wrapped in a structured Pydantic `MCPResult` schema (`success`, `data`, `error`, `message`) by default.
- **Bypass**: To disable wrapping and return raw types (e.g., in legacy clients), set `export DOXYGEN_USE_MCP_RESULT=false`.

### 🖥️ Visual Architecture Reviews
Trigger `generate_architecture_review` to generate a local HTML report.
- Opens in your web browser automatically.
- Contains class structures, coupling graphs, and Mermaid diagrams.
- Verified cryptographically and timestamped.

### ✂️ Surgical Refactoring Tools
- `doxy_references`: Lists all call sites (file, line, content) of any symbol across the workspace.
- `doxy_rename_impact`: Analyzes rename implications (definitions, call sites, subclass breakages).
- `doxy_skeleton`: Returns file structures with all method/function bodies stripped (token-efficient).
- `doxy_virtual_diff`: Detects working tree signature changes and contract breakages.
- `doxy_trace_path`: Chains call path snippets sequentially starting from an entry symbol.

### ⚡ Incremental Delta Refresh
- `doxy_refresh_delta`: Refreshes the XML index for a single file or folder in under a second (bypasses full rebuild latency).

### 🔍 Codebase & Documentation Audits
- `doxy_doc_gaps`: Identifies undocumented public classes and functions (uses AST for Python).
- `doxy_parity_check`: Finds mismatches, redundancies, or missing `@param` documentation tags.
- `doxy_binary_gaps`: Cross-references compiled outputs (`.o` files via `nm`) with headers to locate stubs. Configured via `DOXYGEN_NM_PATH` and `DOXYGEN_BUILD_DIR`.

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
