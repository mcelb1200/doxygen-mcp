"""
Tests for the generate_config function in server.py
"""
import json
import sys
from io import StringIO
from unittest.mock import MagicMock
from doxygen_mcp.server import generate_config

def test_generate_config_gemini_parity():
    """Verify that --gemini flag produces same output as standard for now."""
    args_gemini = MagicMock()
    args_gemini.gemini = True
    args_gemini.path = "/tmp/project"

    args_standard = MagicMock()
    args_standard.gemini = False
    args_standard.path = "/tmp/project"

    # Capture output for gemini=True
    captured_gemini = StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured_gemini
    try:
        generate_config(args_gemini)
    finally:
        sys.stdout = original_stdout

    output_gemini = captured_gemini.getvalue()

    # Capture output for gemini=False
    captured_standard = StringIO()
    sys.stdout = captured_standard
    try:
        generate_config(args_standard)
    finally:
        sys.stdout = original_stdout

    output_standard = captured_standard.getvalue()

    assert output_gemini == output_standard

    # Verify it's valid JSON and has expected structure
    config = json.loads(output_gemini)
    assert "mcpServers" in config
    assert "doxygen-mcp" in config["mcpServers"]
