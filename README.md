# Doxygen MCP Server

A powerful Model Context Protocol (MCP) server that provides AI assistants with deep structural understanding and management of Doxygen-based documentation projects.

**[👉 Quick Start Guide for Users](./USING.md)** | **[🤖 Instructions for AI Agents](./AGENTS.md)**

## 🚀 Overview

The Doxygen MCP Server bridges the gap between source code and AI understanding. By leveraging Doxygen's pre-parsed structural information, it enables AI assistants to:

- **Understand Code Architecture**: Navigate class hierarchies, namespaces, and file structures.
- **Context-Aware Assistance**: Automatically locate symbol definitions based on IDE cursor position.
- **Zero-Config Integration**: Self-configure based on the active IDE workspace and environment.
- **Continuous Documentation**: Effortlessly keep documentation in sync with the live codebase.

## ✨ Features

### 🧠 Context & IDE Awareness

- **IDE Detection**: Automatically identifies if it's running in **Cursor** or **VS Code**.
- **Dynamic Project Discovery**: Resolves the project root using IDE variables like `VSCODE_WORKSPACE_FOLDER` or by searching for Markers (`.git`, `Doxyfile`).
- **Workspace State Tracking**: Integration with IDE-supplied environment variables to track active files and cursor positions.
- **Auto-Project Naming**: Automatically retrieves the project name from IDE variables (e.g., `VSCODE_WORKSPACE_NAME`) or the workspace folder name.

### ⚙️ Self-Configuration

- **Zero-Config XML Discovery**: Automatically locates XML metadata in standard locations (`docs/xml`, `xml`, `doxygen/xml`).
- **Default XML Support**: Enabled by default in all new projects to ensure rich structural queries are available instantly.
- **Environment Overrides**: Every Doxygen setting can be overridden via `DOXYGEN_MCP_<FIELD_NAME>` environment variables.

## 📋 Supported Languages

- **Primary**: C, C++, Python, PHP, Java, C#, JavaScript, TypeScript.
- **Extended**: Any language supported by Doxygen (Go, Rust, Fortran, etc.).

## 🛠️ Prerequisites

- **Python 3.11+**
- **Doxygen** (Essential for structural parsing)
- **uv** (Recommended package manager)
- **Graphviz** (Optional, for relationship graphs)

## 📦 Installation

```bash
# Clone the repository
git clone (https://github.com/mcelb1200/doxygen-mcp)
cd doxygen-mcp

# Install dependencies
uv sync
```

## 🔧 Configuration

### Automagic Configuration (Recommended)

To quickly generate the correct configuration for your MCP client, run:

```bash
# Generate generic MCP configuration (VS Code, etc.)
uv run doxygen-mcp config

# Generate configuration for Gemini CLI
uv run doxygen-mcp config --gemini
```

The command will output a JSON snippet that you can copy directly into your client's configuration file (e.g., `settings.json` for VS Code extensions, or your local `mcp_config.json`).

### Manual Configuration

If you prefer to configure it manually, integrate into your MCP client (Claude Desktop, Cursor, Gemini CLI, etc.) using dynamic path discovery:

```json
{
  "mcpServers": {
    "doxygen-mcp": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/doxygen-mcp",
        "run", "doxygen-mcp"
      ],
      "env": {
        "DOXYGEN_MCP_PROJECT_NAME": "MyAwesomeProject",
        "DOXYGEN_XML_DIR": "./xml"
      }
    }
  }
}
```

> [!TIP]
> Use relative paths like `./xml` for `DOXYGEN_XML_DIR`. The server will resolve them against your active workspace automatically.

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `get_context_info` | Returns information about the detected IDE and project root. |
| `auto_configure` | Detects language and initializes a Doxygen project (wrapper for `create_doxygen_project`). |
| `create_doxygen_project` | Initialize a new Doxygen documentation project with specific settings. |
| `scan_project` | Analyze project structure and identify file types. |
| `generate_documentation` | Triggers a full Doxygen build. |
| `check_doxygen_install` | Verifies that Doxygen is installed and accessible. |
| `get_project_structure` | Provides a high-level map of classes, namespaces, and files. |
| `get_file_structure` | Lists all documented symbols and their locations within a specific file. |
| `get_symbol_at_location` | Finds the symbol context for a specific file/line. |
| `query_active_symbol` | Identifies and queries documentation for the symbol at the current cursor position. |
| `query_project_reference` | Searches for detailed documentation of a symbol (class, function, etc.). |
| `refresh_index` | Updates the server's internal model from disk. |

## 📄 License

This project is licensed under the GNU General Public License version 3 (GPLv3). See [COPYING.md](./COPYING.md) for details.
