# Getting Started: Doxygen MCP

**Doxygen MCP** connects AI (Claude, Cursor, Gemini) to code docs. AI understands structure without reading all files. Faster, smarter.

---

## 🚀 Quick Start
### 1. Install Deps
Need `uv` and `doxygen`.

**Mac:** `brew install doxygen uv`
**Windows:** Doxygen [doxygen.nl](https://www.doxygen.nl/download.html), `uv` via astral.sh.

### 2. Run Setup Script (Recommended)
Run the setup script, passing the target project path. Optionally use `--sanitize` to make configuration paths home-relative (`~`) for privacy:
```bash
./scripts/setup.sh /path/to/target/project [--sanitize]
```
This automatically:
- Installs Python dependencies (including `tree-sitter`).
- Installs `doxygen-mcp` globally via `uv tool install`.
- Locates active client configurations (Claude Desktop, Cursor, VS Code, Google Antigravity), prompts you, backs them up, and updates them.

### 3. Restart
Restart your AI client. The tools will now be active.

---

## 📁 Other Projects & Cross-Repo Context
By default, the server is configured to serve the project specified during setup. To reference other projects or allow cross-repo refactoring context:

**Method A (Project Config file):**
Create a `doxygen_mcp.json` in your project root (see below).

**Method B (Manual Config):**
Generate client config JSON manually for other project paths:
`doxygen-mcp config --path "/path/to/other/project"`

### 📁 Project-level Allowed Paths & Doxygen Settings (doxygen_mcp.json)
To allow a single global server instance to safely access other projects, dependencies, or to hardcode Doxygen output folders, create a `doxygen_mcp.json` file in your project's root folder. Path values support `~` and env variable expansion:
```json
{
  "allowed_paths": [
    "~/github/other-project",
    "../relative-neighbor-project"
  ],
  "xml_dir": "docs/xml"
}
```

> [!NOTE]
> The setup script automatically configures the project to ignore `doxygen_mcp.json` and other doxygen-mcp patterns in `.gitignore` (Option 2) under a dedicated section header (`# Doxygen MCP Server`) to avoid committing absolute local paths.

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
Background Doxygen updates on commit/push. Fully compatible with Git worktrees.

### 1. Install
Run in project root:
`python path/to/scripts/install_hooks.py`

Hooks are installed under the resolved git hooks directory (supporting worktree paths using `git rev-parse --git-path hooks` to locate `.git/common/hooks` automatically).

### 2. Result
- **Commit**: Fast incremental update on header change.
- **Push**: Full build (graphs/refs).
