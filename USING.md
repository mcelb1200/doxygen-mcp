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
**"No Doxyfile"**: Ask AI: *"Configure project for me"*. Runs `auto_configure`.
**"Symbol not found"**: Ask AI: *"Refresh index"*. Runs `refresh_index`.

---

## 🔄 Auto-Sync (Git Hooks)
Background Doxygen updates on commit/push.

### 1. Install
Run in project root:
`python path/to/scripts/install_hooks.py`

### 2. Result
- **Commit**: Fast incremental update on header change.
- **Push**: Full build (graphs/refs).
