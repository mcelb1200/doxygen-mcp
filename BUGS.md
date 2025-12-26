# Bug Reports and Troubleshooting

This document covers bug reporting procedures and common troubleshooting steps. For security issues, see the SECURITY file.

## Reporting Bugs

To report a bug, please open an issue on the GitHub repository with the following information:

- **Clear Title**: Brief description of the issue
- **Detailed Description**: Step-by-step instructions to reproduce the bug
- **Expected vs Actual Behavior**: What should happen vs what actually happens
- **Version Information**: Software version (`uv run python -c "import doxygen_mcp; print(doxygen_mcp.__version__)"`)
- **Environment Details**:
  - Operating system (Windows/macOS/Linux)
  - Python version (`python --version`)
  - Doxygen version (`doxygen --version`)
  - uv version (`uv --version`)
- **Error Messages**: Complete error output or log files
- **Configuration**: Your MCP client configuration (sanitized)

## Troubleshooting

### Common Issues

#### Doxygen Not Found

**Symptom**: Error message "❌ Doxygen not found. Please install Doxygen first."

**Solution**:
```bash
# Verify Doxygen installation
doxygen --version

# If not installed:
# Ubuntu/Debian
sudo apt-get install doxygen

# macOS
brew install doxygen

# Windows - add to PATH if needed
set PATH=%PATH%;C:\Program Files\doxygen\bin
```

#### Graphviz Diagrams Not Working

**Symptom**: Diagrams are missing or not generated in documentation

**Solution**:
```bash
# Test Graphviz installation
dot -V

# Install if missing:
# Ubuntu/Debian
sudo apt-get install graphviz graphviz-dev

# macOS
brew install graphviz

# Windows
# Download from https://graphviz.org/download/

# In Doxyfile, ensure:
HAVE_DOT = YES
DOT_PATH = /path/to/graphviz/bin  # if not in PATH
```

#### LaTeX PDF Generation Fails

**Symptom**: HTML documentation works but PDF generation fails

**Solution**:
```bash
# Test LaTeX installation
pdflatex --version

# Install LaTeX:
# Ubuntu/Debian
sudo apt-get install texlive-latex-extra texlive-fonts-recommended

# macOS
brew install --cask mactex

# Windows
# Download MiKTeX from https://miktex.org/

# Additional packages may be needed:
sudo tlmgr install collection-latexextra
```

#### Permission Errors

**Symptom**: "Permission denied" when generating documentation

**Solutions**:
- Ensure write permissions to output directory:
  ```bash
  chmod -R u+w /path/to/output/directory
  ```
- Check project path is accessible by the MCP server
- Run with appropriate user privileges (avoid running as root)
- Verify file system permissions for the working directory

#### MCP Server Not Starting

**Symptom**: Claude Desktop shows "Server disconnected" or timeout errors

**Solutions**:

1. **Verify installation**:
   ```bash
   uv sync
   uv run doxygen-mcp
   ```

2. **Check configuration**:
   - Ensure absolute paths in `claude_desktop_config.json`
   - Verify `uv` is in system PATH
   - Check for typos in command or args

3. **Test manually**:
   ```bash
   # Should start without errors
   timeout 3 uv run doxygen-mcp || echo "OK - server started"
   ```

4. **Check logs**:
   - Windows: `%APPDATA%\Claude\logs\`
   - macOS: `~/Library/Logs/Claude/`
   - Linux: `~/.config/Claude/logs/`

#### Module Not Found Errors

**Symptom**: `ModuleNotFoundError: No module named 'doxygen_mcp'`

**Solutions**:
```bash
# Reinstall dependencies
uv sync

# Verify package is installed
uv run python -c "import doxygen_mcp; print('OK')"

# If still failing, check you're in project root
cd /path/to/doxygen-mcp
uv sync
```

#### Documentation Generation Is Slow

**Symptom**: Doxygen takes a long time to process large projects

**Performance Tips**:

1. **Optimize Doxyfile settings**:
   ```conf
   EXTRACT_ALL            = NO    # Only document annotated code
   EXTRACT_PRIVATE        = NO    # Skip private members
   RECURSIVE              = YES   # But use EXCLUDE_PATTERNS
   EXCLUDE_PATTERNS       = */build/* */vendor/* */node_modules/*
   MAX_DOT_GRAPH_DEPTH    = 3     # Limit diagram complexity
   DOT_GRAPH_MAX_NODES    = 50    # Prevent huge diagrams
   ```

2. **Use file patterns wisely**:
   ```conf
   FILE_PATTERNS = *.h *.hpp *.cpp  # Only source files, not logs/data
   ```

3. **Disable unnecessary features**:
   ```conf
   CALL_GRAPH             = NO    # Expensive for large codebases
   CALLER_GRAPH           = NO    # Expensive for large codebases
   SOURCE_BROWSER         = NO    # Skip if not needed
   ```

### Debug Mode

For detailed diagnostic information:

**Enable verbose logging**:
```bash
# Set environment variable for debug output
export PYTHONUNBUFFERED=1
export MCP_DEBUG=1

# Run server with debug logging
uv run python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from doxygen_mcp.server import main
main()
"
```

**Check MCP protocol messages**:
Use [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to debug communication:
```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/doxygen-mcp run doxygen-mcp
```

### Getting Help

If you can't resolve your issue:

1. Check existing [GitHub Issues](https://github.com/positronikal/doxygen-mcp/issues)
2. Review the [USING.md](./USING.md) documentation
3. Open a new issue with complete details (see "Reporting Bugs" above)
4. For security issues, see SECURITY.md for responsible disclosure

### Prerequisites Checklist

Before reporting a bug, verify you have:

- ✅ Python 3.11 or later installed
- ✅ uv package manager installed
- ✅ Doxygen installed and in PATH
- ✅ Project dependencies installed (`uv sync`)
- ✅ Correct MCP client configuration (absolute paths)
- ✅ Write permissions to output directories
- ✅ (Optional) Graphviz for diagrams
- ✅ (Optional) LaTeX for PDF generation
