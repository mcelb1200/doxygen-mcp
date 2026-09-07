# Doxygen MCP Server

MCP server for deep structural understanding Doxygen projects.

**[👉 User Guide](./USING.md)** | **[🤖 Agent Instructions](./AGENTS.md)**

## 🚀 Overview
Bridges source code and AI. Enables:
- **Code Architecture**: hierarchy, namespaces, file maps.
- **Context-Aware**: symbol location via IDE cursor.
- **Zero-Config**: self-config based on workspace.
- **Live Docs**: sync with live code.

## ✨ Features
### 🧠 IDE Awareness
- **Detection**: Cursor, VS Code.
- **Discovery**: Dynamic root resolution (`.git`, `Doxyfile`).
- **State**: Track active files, cursor positions.

### ⚙️ Self-Config
- **XML Discovery**: Auto-locate `docs/xml`, `xml`.
- **Overrides**: Use `DOXYGEN_MCP_<FIELD>` env vars.

## 📋 Languages
- **Primary**: C, C++, Python, PHP, Java, C#, JS, TS.
- **Doxygen supported**: Go, Rust, Fortran, etc.

## 🛠️ Prerequisites
- **Python 3.11+**
- **Doxygen** (Required)
- **uv** (Recommended)
- **Graphviz** (Optional)

## 📦 Installation & Setup
Automatically configures Python dependencies (including `tree-sitter`), installs `doxygen-mcp` globally, and registers it into active AI clients (**Claude Desktop**, **Cursor**, **VS Code**, and **Google Antigravity**).

### 1. Run Setup Wizard
Clone the repository and run the setup script. Optionally, pass a target project path, and `--sanitize` to make client configuration paths home-relative (`~`) for privacy and portability:
```bash
# Linux / macOS / WSL
git clone https://github.com/mcelb1200/doxygen-mcp
cd doxygen-mcp
./scripts/setup.sh [/optional/target/project/path] [--sanitize]

# Windows
.\scripts\setup.ps1 [-path \optional\target\path] [-sanitize]
```

The script will locate active client configurations on your system, back them up, and insert the `doxygen-mcp` settings automatically.

### 2. Manual Config (Optional)
If no clients are auto-detected, or you want to generate manual configuration blocks for other projects:
```bash
# Output Claude configuration JSON
doxygen-mcp config --path /path/to/project

# Output Gemini/Antigravity config JSON
doxygen-mcp config --gemini --path /path/to/project
```

## 🧰 CLI Utilities
In addition to the MCP server daemon, the package provides standalone CLI executables:
* **`doxygen-mcp`**: Core Model Context Protocol server (supports MCP Python SDK v1 and v2 `MCPServer`). Includes helper commands like `doxygen-mcp config --gemini --path <project>`.
* **`doxygen-snr-filter [xml_dir]`**: High-speed XML Signal-to-Noise Ratio (SNR) minifier. Strips non-semantic XML tags and repetitive metadata to compress Doxygen XML payloads for token-efficient LLM ingestion.
* **`doxygen-setup-funnel [repo_path]`**: Automated hook and configuration funnel installer. Mounts optimized `Doxyfile.fast` and Git worktree-aware commit hooks (`post-commit`, `pre-push`) to keep XML indexes continuously in sync.

## 🛠️ Tools
| Tool | Purpose |
|------|---------|
| `doxy_context` | IDE & root info. |
| `doxy_config` | Detect lang & init. |
| `doxy_scan` | Analyze file types. |
| `doxy_generate` | Run Doxygen. |
| `doxy_structure` | Class/namespace map. |
| `doxy_query` | Symbol documentation. |
| `doxy_active` | Symbol at cursor info. |
| `generate_context_report` | Multi-source LLM context report (git, diff, layout). |
| `generate_architecture_review` | Visual HTML review. Opens browser. |
| `doxy_doc_gaps` | Scan codebase for undocumented symbols (uses AST for Python). |
| `doxy_binary_gaps` | Scan build objects for compiled symbol gaps. |
| `doxy_references` | Find symbol call sites and occurrences. |
| `doxy_rename_impact` | Predict rename breakages (callers, subclasses). |
| `doxy_parity_check` | Find mismatched, redundant, or missing `@param` tags. |
| `doxy_refresh_delta` | Fast incremental refresh of single file or folder index. |
| `doxy_skeleton` | Get file structural signatures with bodies stripped. |
| `doxy_virtual_diff` | Diff working tree signatures against index for API breakages. |
| `doxy_trace_path` | Trace call path chains sequentially to debug execution. |

## ⚙️ Configuration Options
* **`DOXYGEN_PROJECT_ROOT`**: Root path of target project to document (supports `~` and env variable expansion).
* **`DOXYGEN_ALLOWED_PATHS`**: Comma-separated directories that the MCP server is authorized to read.
* **`DOXYGEN_USE_MCP_RESULT`**: Wrap tool responses in structured Pydantic `MCPResult` schema (`success`, `data`, `error`, `message`). Defaults to `true` (except in pytest).
* **`DOXYGEN_COMPRESS_OUTPUT`**: Toggle global output token compression (Token Crusher Middleware). Defaults to `true`. Set to `false` in local env config to disable compression.
* **`DOXYGEN_NM_PATH`**: Explicit path to `nm`/`llvm-nm` executable for linkage audits.
* **`DOXYGEN_BUILD_DIR`**: Path containing compiled object files (`.o`, `.obj`) to scan.

## 📁 Multi-Project Context Safety (doxygen_mcp.json)
To allow a single global server instance to safely reference neighbor projects or specify Doxygen output settings, create a `doxygen_mcp.json` file in your project root. Path values support `~` and env variable expansion:
```json
{
  "allowed_paths": [
    "~/github/other-project",
    "../dependency-folder"
  ],
  "xml_dir": "docs/xml"
}
```

> [!NOTE]
> The setup script automatically configures the project to ignore `doxygen_mcp.json` and other doxygen-mcp patterns in `.gitignore` (Option 2) under a dedicated section header (`# Doxygen MCP Server`) to avoid committing absolute local paths.

## 🛡️ Security
- **Path Protection**: Restrict access to project root.
- **Symlink Safety**: No symbolic link following for writes.
- **Safe Config**: No `Doxyfile` overwrite.

## 📄 License
GPLv3. See [COPYING](./COPYING).
