# Getting Started with Doxygen MCP

**Doxygen MCP** is a bridge that connects your AI assistant (like Claude, Cursor, or Gemini) to your code's documentation. It helps the AI understand your project's structure, classes, and functions without reading every single file, making it faster and smarter.

---

## 🚀 Quick Start (In 3 Steps)

### 1. Install Dependencies
You need `uv` (a fast Python tool) and `doxygen` (the documentation engine).

**Mac (Homebrew):**
```bash
brew install doxygen uv
```

**Windows:**
1. Download Doxygen: [doxygen.nl/download.html](https://www.doxygen.nl/download.html)
2. Install `uv`: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### 2. Configure Your AI Client
Run this one command in your terminal to generate the configuration for your favorite AI tool:

**For Claude Desktop:**
```bash
# In the doxygen-mcp folder
uv run doxygen-mcp config
```

Copy the output (JSON text) into your Claude Desktop config file.

**For Gemini CLI:**
```bash
uv run doxygen-mcp config --gemini
```

### 3. Connect & Go
Restart your AI client. You should now see the `doxygen-mcp` tools available.

---

## 📁 Using with Other Projects

By default, the server looks at the directory where it's running. To use it with a **different project** or repository:

### Method A: Configuration Flag (Recommended)
Generate a config specifically for another path:
```bash
uv run doxygen-mcp config --path "/path/to/my/other-project"
```

### Method B: Run Script
If you are running the server locally for testing:
```bash
./scripts/run.sh "/path/to/my/other-project"
```

### Method C: Environment Variables
You can manually set these variables in your MCP client configuration:
- `DOXYGEN_PROJECT_ROOT`: The absolute path to the project you want to document.
- `DOXYGEN_ALLOWED_PATHS`: A comma-separated list of paths the server is allowed to access (for security).

---

## 🤖 How to Use It (For AI Users)

Once connected, you don't need to run commands manually. Just ask your AI questions like:

*   "How is this project structured?"
*   "Explain the `UserAuthentication` class."
*   "What functions are in `server.py`?"
*   "Generate documentation for my current file."

The AI will automatically use the tools (`get_project_structure`, `query_project_reference`, etc.) to find the answers.

---

## 🛠️ Troubleshooting

**"Doxygen not found"**
*   Make sure you installed Doxygen (Step 1).
*   Try running `doxygen --version` in your terminal. If it fails, add the Doxygen `bin` folder to your system PATH.

**AI says "No Doxyfile found"**
*   The AI can fix this! Just ask it: *"Please configure the project for me."*
*   It will run the `auto_configure` tool to set everything up.

**"Symbol not found"**
*   If you just added new code, ask the AI to *"Refresh the index"* (it runs `refresh_index`).

---

## 📚 Technical Reference

For advanced users, developers, and contributors:

*   **[README.md](./README.md)**: Full technical overview, architecture, and manual configuration.
*   **[AGENTS.md](./AGENTS.md)**: Instructions on how AI agents use this tool internally.
*   **[BUGS.md](./BUGS.md)**: Known issues and reporting guide.

---

## 🔄 Keeping the Index in Sync Automatically

To ensure your AI assistant always has the latest information without manual refreshes, you can install **Git Hooks**. These will trigger background Doxygen updates whenever you commit or push code.

### 1. Install Hooks
In the root of your project (where your .git folder is), run:

```bash
# Using the install script from the doxygen-mcp folder
python path/to/doxygen-mcp/scripts/install_hooks.py
```

### 2. What Happens Next?
- **On Commit**: If you change any header files (.h, .hpp), a **fast incremental update** runs in the background. It skips heavy diagram generation to keep your workflow fast.
- **On Push**: A **full documentation build** runs in the background, updating all cross-references and graphs.

This ensures that doxygen-mcp is always synchronized with your latest architectural changes.
