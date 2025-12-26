# procexec-inspector.ps1
# Simplified MCP Inspector launcher for ProcExecMCP
# Launches from the project directory directly

param(
    [string]$ServerPath = $null
)

Write-Host "=== ProcExecMCP Inspector Launcher ===" -ForegroundColor Cyan
Write-Host ""

# Determine server directory
if ($ServerPath) {
    $repoRoot = Resolve-Path $ServerPath
} else {
    $repoRoot = Get-Location
}

Write-Host "Project: $repoRoot" -ForegroundColor Yellow
Write-Host ""

# Verify we're in the right directory
$pyprojectToml = Join-Path $repoRoot "pyproject.toml"
if (-not (Test-Path $pyprojectToml)) {
    Write-Host "✗ Not a valid ProcExecMCP project directory!" -ForegroundColor Red
    Write-Host "   Missing: pyproject.toml" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Detected ProcExecMCP project" -ForegroundColor Green
Write-Host ""
Write-Host "Starting MCP Inspector..." -ForegroundColor Cyan
Write-Host "Inspector will open in your browser" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Change to project directory and launch
Push-Location $repoRoot
try {
    # Launch inspector - uv will find pyproject.toml in current directory
    & npx @modelcontextprotocol/inspector uv run procexec
} finally {
    Pop-Location
}
