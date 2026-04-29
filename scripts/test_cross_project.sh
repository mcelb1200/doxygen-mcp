#!/bin/bash
# Test script to verify doxygen-mcp can run against a different project directory

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Create a dummy project in /tmp
TEST_PROJECT="/tmp/doxygen_test_project"
echo "Setting up test project in $TEST_PROJECT..."
rm -rf "$TEST_PROJECT"
mkdir -p "$TEST_PROJECT/src"

cat <<EOF > "$TEST_PROJECT/src/hello.cpp"
/**
 * @brief A simple greeting function.
 * @param name The name of the person to greet.
 */
void say_hello(const char* name) {
    // hello
}
EOF

# 2. Run doxygen-mcp against the test project
# We use -c to just run a quick command and exit if possible, 
# but here we'll use the CLI tools if we had a non-interactive mode.
# Since it's an MCP server, we'll verify it can at least START and resolve the path.

echo "Verifying path resolution..."
# Use uv run to execute a small python snippet that imports and resolves
export DOXYGEN_PROJECT_ROOT="$TEST_PROJECT"
export DOXYGEN_ALLOWED_PATHS="/tmp"

RESULT=$(uv run python3 -c "from doxygen_mcp.utils import resolve_project_path; print(resolve_project_path())")

if [ "$RESULT" == "$TEST_PROJECT" ]; then
    echo -e "${GREEN}Path resolution successful! Resolved to: $RESULT${NC}"
else
    echo -e "${RED}Path resolution failed! Expected $TEST_PROJECT, got $RESULT${NC}"
    exit 1
fi

# 3. Clean up
rm -rf "$TEST_PROJECT"
echo "Cleanup complete."
