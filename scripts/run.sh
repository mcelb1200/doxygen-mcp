#!/bin/bash

# Runner script for Doxygen MCP Server
set -e

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check for uv
if ! command -v uv &> /dev/null; then
    # Check common local path
    if [ -f "$HOME/.local/bin/uv" ]; then
        UV_BIN="$HOME/.local/bin/uv"
    else
        echo -e "${RED}Error: 'uv' not found.${NC}"
        echo "Please run ./scripts/setup.sh first."
        exit 1
    fi
else
    UV_BIN=$(command -v uv)
fi

# Ensure dependencies are synced if .venv is missing
if [ ! -d ".venv" ]; then
    echo -e "${CYAN}Virtual environment missing. Running setup...${NC}"
    ./scripts/setup.sh
fi

# Support passing project path as first argument
if [ -d "$1" ]; then
    PROJECT_PATH=$(realpath "$1")
    shift
    echo -e "${CYAN}Targeting project: $PROJECT_PATH${NC}"
    export DOXYGEN_PROJECT_ROOT="$PROJECT_PATH"
    export DOXYGEN_ALLOWED_PATHS="$(dirname "$PROJECT_PATH"),$PROJECT_PATH"
fi

echo -e "${GREEN}Starting Doxygen MCP Server...${NC}"
$UV_BIN run doxygen-mcp "$@"
