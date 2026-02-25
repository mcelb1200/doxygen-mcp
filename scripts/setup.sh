#!/bin/bash

# Setup script for Doxygen MCP Server (Bash/Linux/WSL/Git Bash)
set -e

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${CYAN}============================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}============================================================${NC}\n"
}

print_success() { echo -e " ${GREEN}[OK]${NC} $1"; }
print_error() { echo -e " ${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e " ${YELLOW}[WARN]${NC} $1"; }

print_header "Doxygen MCP Server - Setup Wizard (Bash)"

# 1. Check/Install uv
if ! command -v uv &> /dev/null; then
    print_warning "'uv' package manager not found."
    echo "Attempting to install uv..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        # Update current path
        export PATH="$HOME/.local/bin:$PATH"
        # Also try to find where it was likely installed if not in path yet
        if [ -f "$HOME/.local/bin/uv" ]; then
            UV_BIN="$HOME/.local/bin/uv"
        else
            UV_BIN="uv"
        fi
        print_success "uv installed successfully."
    else
        print_error "Failed to install uv automatically."
        echo "Please install it manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
else
    print_success "'uv' is already installed."
    UV_BIN=$(command -v uv)
    # Ensure it is up to date
    $UV_BIN self update &> /dev/null || true
fi

# 2. Check/Install Python via uv
print_header "Checking Python Environment"
if $UV_BIN python find ">=3.11" &> /dev/null; then
    py_ver=$($UV_BIN python find ">=3.11")
    print_success "Compatible Python found: $py_ver"
else
    print_warning "No compatible Python (>=3.11) found. Attempting to install via uv..."
    if $UV_BIN python install 3.11; then
        print_success "Python 3.11 installed via uv."
    else
        print_error "Failed to install Python 3.11."
        exit 1
    fi
fi

# 3. Check Doxygen
if ! command -v doxygen &> /dev/null; then
    print_warning "Doxygen is not in your PATH."
    echo "It is required for generating documentation."
    echo "  - Ubuntu/Debian: sudo apt install doxygen"
    echo "  - macOS: brew install doxygen"
    echo "  - Windows (Git Bash): Download from doxygen.nl"
else
    version=$(doxygen --version)
    print_success "Doxygen found (Version: $version)"
fi

# 4. Check Graphviz
if ! command -v dot &> /dev/null; then
    print_warning "Graphviz (dot) not found."
    echo "  Required for generating diagrams."
    echo "  - Ubuntu/Debian: sudo apt install graphviz"
    echo "  - macOS: brew install graphviz"
else
    print_success "Graphviz found (dot command available)"
fi

# 5. Install Project Dependencies
print_header "Installing Python Dependencies"
echo "Running 'uv sync' (this may take a moment)..."
if $UV_BIN sync; then
    print_success "Dependencies installed successfully."
else
    print_warning "uv sync failed. Attempting with --no-cache..."
    if $UV_BIN sync --no-cache; then
        print_success "Dependencies installed successfully (without cache)."
    else
        print_error "Failed to sync dependencies. Check your internet connection."
        echo "If the issue persists, try deleting the .venv directory and running this script again."
        exit 1
    fi
fi

# 6. Verification
print_header "Verifying Installation"
if $UV_BIN run python -c "import doxygen_mcp; print(doxygen_mcp.__version__)" &> /dev/null; then
    version=$($UV_BIN run python -c "import doxygen_mcp; print(doxygen_mcp.__version__)")
    print_success "Server Verified: doxygen-mcp v$version"
    
    echo -e "\n${GREEN}Setup Complete!${NC}\n"
    
    PROJ_DIR=$(pwd)
    
    echo "To configure this server in your IDE:"
    echo "-----------------------------------"
    echo -e "Command: ${CYAN}$UV_BIN${NC}"
    echo -e "Args:    ${CYAN}--directory \"$PROJ_DIR\" run doxygen-mcp${NC}"
else
    print_error "Server failed to start. Try running 'uv sync' again."
    exit 1
fi
