# Bug Reports & Troubleshooting

Report bugs on GitHub. For security, see SECURITY file.

## Reporting Bugs
Open GitHub issue. Include:
- **Title**: Brief issue description.
- **Steps**: Instructions to reproduce.
- **Behavior**: Expected vs Actual.
- **Version**: `uv run python -c "import doxygen_mcp; print(doxygen_mcp.__version__)"`.
- **Env**: OS, Python, Doxygen, uv versions.
- **Logs**: Error output/logs.
- **Config**: Sanitized MCP config.

## Troubleshooting
### Doxygen Not Found
**Symptom**: "Doxygen not found" error.
**Solution**:
- `doxygen --version` check.
- Install: `apt install doxygen` (Ubuntu), `brew install doxygen` (Mac).
- Windows: Add `bin` to PATH.

### Graphviz Failing
**Symptom**: Missing diagrams.
**Solution**:
- `dot -V` check.
- Install: `apt install graphviz`, `brew install graphviz`.
- Doxyfile: `HAVE_DOT = YES`.

### LaTeX PDF Fails
**Symptom**: HTML works, PDF fails.
**Solution**:
- `pdflatex --version` check.
- Install: `texlive-latex-extra` (Ubuntu), `mactex` (Mac), MiKTeX (Windows).

### Permission Errors
**Symptom**: "Permission denied".
**Solution**:
- `chmod -R u+w` output dir.
- Verify server has access to project path.

### MCP Server Disconnected
**Solution**:
- Verify: `uv sync`, `uv run doxygen-mcp`.
- Config: Use absolute paths in `claude_desktop_config.json`.
- Logs: Check `%APPDATA%\Claude\logs\` (Win) or `~/Library/Logs/Claude/` (Mac).

### Module Not Found
**Solution**:
- `uv sync` to reinstall deps.
- Check project root.

### Slow Generation
**Tips**:
- `EXTRACT_PRIVATE = NO`.
- `EXCLUDE_PATTERNS = */build/* */node_modules/*`.
- `MAX_DOT_GRAPH_DEPTH = 3`.
- `FILE_PATTERNS = *.h *.cpp`.

### Debug Mode
**Verbose Log**:
```bash
export PYTHONUNBUFFERED=1
export MCP_DEBUG=1
# Run with logging.DEBUG
```
**MCP Inspector**:
`npx @modelcontextprotocol/inspector uv --directory /path/to/doxygen-mcp run doxygen-mcp`

### Help
1. Check [GitHub Issues](https://github.com/positronikal/doxygen-mcp/issues).
2. Read [USING.md](./USING.md).
3. Open issue with details.
