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

## 📦 Installation
### Linux / macOS / WSL
```bash
git clone https://github.com/mcelb1200/doxygen-mcp
cd doxygen-mcp
./scripts/setup.sh
```

### Windows
```powershell
.\scripts\setup.ps1
```

## 🚀 Run
```bash
./scripts/run.sh
# OR
uv run doxygen-mcp
```

## 📂 Target Other Projects
### 1. Config
```bash
uv run doxygen-mcp config --path /project/path
```

### 2. Manual
Set `DOXYGEN_PROJECT_ROOT` env var.

## 🔧 Config
### Auto (Recommended)
```bash
uv run doxygen-mcp config
# For Gemini
uv run doxygen-mcp config --gemini
```

## 🛠️ Tools
| Tool | Purpose |
|------|---------|
| `get_context_info` | IDE & root info. |
| `auto_configure` | Detect lang & init. |
| `scan_project` | Analyze file types. |
| `generate_documentation` | Run Doxygen. |
| `get_project_structure` | Class/namespace map. |
| `query_project_reference` | Symbol documentation. |
| `query_active_symbol` | Symbol at cursor info. |

## 🛡️ Security
- **Path Protection**: Restrict access to project root.
- **Symlink Safety**: No symbolic link following for writes.
- **Safe Config**: No `Doxyfile` overwrite.

## 📄 License
GPLv3. See [COPYING.md](./COPYING.md).
