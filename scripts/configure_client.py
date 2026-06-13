#!/usr/bin/env python3
"""
configure_client.py - Automated setup and client configuration for doxygen-mcp
"""
import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

CLIENTS = {
    "Claude Desktop": {
        "paths": {
            "darwin": "~/Library/Application Support/Claude/claude_desktop_config.json",
            "linux": "~/.config/Claude/claude_desktop_config.json",
            "win32": "%APPDATA%/Claude/claude_desktop_config.json"
        }
    },
    "Cursor": {
        "paths": {
            "darwin": "~/Library/Application Support/Cursor/User/globalStorage/storage.json",
            "linux": "~/.config/Cursor/User/globalStorage/storage.json",
            "win32": "%APPDATA%/Cursor/User/globalStorage/storage.json"
        }
    },
    "VS Code (Cline)": {
        "paths": {
            "darwin": "~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            "linux": "~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            "win32": "%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
        }
    },
    "VS Code (Roo Code)": {
        "paths": {
            "darwin": "~/Library/Application Support/Code/User/globalStorage/roodev.roprompt-dev/settings/roo_mcp_settings.json",
            "linux": "~/.config/Code/User/globalStorage/roodev.roprompt-dev/settings/roo_mcp_settings.json",
            "win32": "%APPDATA%/Code/User/globalStorage/roodev.roprompt-dev/settings/roo_mcp_settings.json"
        }
    },
    "Google Antigravity": {
        "paths": {
            "darwin": "~/.gemini/antigravity/mcp_config.json",
            "linux": "~/.gemini/antigravity/mcp_config.json",
            "win32": "~/.gemini/antigravity/mcp_config.json"
        }
    }
}

def resolve_path(path_str: str) -> Path:
    if "%APPDATA%" in path_str:
        appdata = os.environ.get("APPDATA", "")
        path_str = path_str.replace("%APPDATA%", appdata)
    
    path = Path(path_str).expanduser()
    return path

def install_standalone_tool():
    """Attempt to install the tool globally using 'uv tool install'."""
    print("Installing doxygen-mcp as a global standalone command via uv tool install...")
    repo_root = Path(__file__).resolve().parent.parent
    
    # Try running uv tool install
    uv_bin = shutil.which("uv")
    if uv_bin:
        try:
            import subprocess
            subprocess.run([uv_bin, "tool", "install", "--force", str(repo_root)], check=True)
            print("Successfully installed doxygen-mcp globally.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"uv tool install failed: {e}. Falling back to repository path execution.")
    return False

def configure_client(client_name: str, config_path: Path, target_project: Optional[Path], repo_root: Path, interactive: bool):
    print(f"\nFound configuration directory for {client_name} at: {config_path.parent}")
    
    if interactive:
        ans = input(f"Do you want to configure/update doxygen-mcp for {client_name}? (y/N): ")
        if ans.lower() not in ('y', 'yes'):
            print(f"Skipped {client_name}.")
            return
            
    # Create config folder if missing
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Backup existing file
    if config_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = config_path.with_suffix(f".json.bak.{timestamp}")
        try:
            shutil.copy2(config_path, backup_path)
            print(f"  Backup created: {backup_path.name}")
        except OSError as e:
            print(f"  Failed to create backup: {e}")
            return
            
    # Load JSON
    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError:
            print(f"  Warning: {config_path.name} was not valid JSON. Starting fresh.")
            
    if "mcpServers" not in config_data or not isinstance(config_data["mcpServers"], dict):
        config_data["mcpServers"] = {}
        
    # Check if doxygen-mcp command is globally in PATH
    mcp_bin = shutil.which("doxygen-mcp")
    if mcp_bin:
        cmd = "doxygen-mcp"
        args = []
    else:
        # Fallback to local uv execution from repo root
        cmd = "uv"
        args = ["--directory", str(repo_root), "run", "doxygen-mcp"]
        
    env = {
        "DOXYGEN_XML_DIR": "./docs/xml"
    }
    if target_project:
        env["DOXYGEN_PROJECT_ROOT"] = str(target_project)
        env["DOXYGEN_ALLOWED_PATHS"] = f"{target_project.parent},{target_project}"
        
    config_data["mcpServers"]["doxygen-mcp"] = {
        "command": cmd,
        "args": args,
        "env": env,
        "disabled": False
    }
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"  Successfully updated {client_name} configuration!")
    except OSError as e:
        print(f"  Error writing config: {e}")

def main():
    parser = argparse.ArgumentParser(description="Configure doxygen-mcp clients")
    parser.add_argument("path", nargs="?", default=None, help="Target project root directory (default: CWD-aware dynamic mode)")
    parser.add_argument("--non-interactive", action="store_true", help="Run automatically without prompting")
    args = parser.parse_args()
    
    target_project = Path(args.path).resolve() if args.path else None
    repo_root = Path(__file__).resolve().parent.parent
    
    # 1. Install tool globally
    install_standalone_tool()
    
    # 1.5 Install skill globally for Antigravity if global skills folder exists
    global_skills_dir = Path("~/.gemini/skills").expanduser()
    if global_skills_dir.exists():
        src_skill = repo_root / "skills" / "doxygen_investigation"
        dst_skill = global_skills_dir / "doxygen_investigation"
        if src_skill.exists():
            try:
                if dst_skill.exists():
                    shutil.rmtree(dst_skill)
                shutil.copytree(src_skill, dst_skill)
                print(f"Successfully installed doxygen-investigation skill to: {dst_skill}")
            except Exception as e:
                print(f"Failed to install skill to ~/.gemini/skills: {e}")
    
    # 2. Iterate clients and update configs
    platform = sys.platform
    configured_any = False
    
    for client_name, client_info in CLIENTS.items():
        path_template = client_info["paths"].get(platform)
        if not path_template:
            continue
            
        config_path = resolve_path(path_template)
        # We configure if either the config file already exists, or the parent directory exists
        if config_path.exists() or config_path.parent.exists():
            configure_client(client_name, config_path, target_project, repo_root, not args.non_interactive)
            configured_any = True
            
    # 3. Create target doxygen_mcp.json if it doesn't exist
    if target_project:
        target_config = target_project / "doxygen_mcp.json"
        if not target_config.exists():
            try:
                default_config = {
                    "allowed_paths": [
                        ".."
                    ]
                }
                with open(target_config, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
                print(f"\nCreated default project configuration at: {target_config}")
            except OSError:
                pass
            
    if not configured_any:
        print("\nNo active MCP clients (Claude Desktop, Cursor, VS Code, Antigravity) detected in standard locations.")
        print(f"To configure manually, copy the following JSON into your MCP settings file:")
        print("----------------------------------------------------------------------")
        # Generate the manual config structure
        mcp_bin = shutil.which("doxygen-mcp")
        if mcp_bin:
            cmd = "doxygen-mcp"
            cmd_args = []
        else:
            cmd = "uv"
            cmd_args = ["--directory", str(repo_root), "run", "doxygen-mcp"]
            
        manual_env = {
            "DOXYGEN_XML_DIR": "./docs/xml"
        }
        if target_project:
            manual_env["DOXYGEN_PROJECT_ROOT"] = str(target_project)
            manual_env["DOXYGEN_ALLOWED_PATHS"] = f"{target_project.parent},{target_project}"
            
        manual_config = {
            "doxygen-mcp": {
                "command": cmd,
                "args": cmd_args,
                "env": manual_env
            }
        }
        print(json.dumps(manual_config, indent=2))
        print("----------------------------------------------------------------------")

if __name__ == "__main__":
    main()
