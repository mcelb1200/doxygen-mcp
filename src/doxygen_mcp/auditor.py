import ast
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import defusedxml.ElementTree as ET
from .query_engine import DoxygenQueryEngine

class PythonDocVisitor(ast.NodeVisitor):
    """AST Visitor to scan Python code for missing docstrings."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.gaps: List[Dict[str, str]] = []
        self._current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        # Skip private classes
        if node.name.startswith('_') and not node.name.startswith('__'):
            self.generic_visit(node)
            return

        doc = ast.get_docstring(node)
        if not doc or not doc.strip():
            self.gaps.append({
                "file": self.filepath,
                "line": node.lineno,
                "symbol": node.name,
                "kind": "class",
                "message": f"Class '{node.name}' is missing docstring"
            })

        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function(node)

    def _check_function(self, node: Any):
        # Skip private methods and magic methods (starts with _ and ends with __ if double-underscore)
        if node.name.startswith('_'):
            if not node.name.startswith('__') or node.name.endswith('__'):
                return

        doc = ast.get_docstring(node)
        if not doc or not doc.strip():
            name = f"{self._current_class}.{node.name}" if self._current_class else node.name
            self.gaps.append({
                "file": self.filepath,
                "line": node.lineno,
                "symbol": name,
                "kind": "function" if not self._current_class else "method",
                "message": f"Method/Function '{name}' is missing docstring"
            })

def audit_python_files(project_path: Path) -> List[Dict[str, Any]]:
    """Scan all Python files in the project path recursively for missing docstrings."""
    gaps = []
    for root, _, files in os.walk(project_path):
        # Skip standard venv/cache directories
        if any(p in root for p in ['venv', 'env', '.venv', '.git', '__pycache__', 'build', 'dist']):
            continue
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding='utf-8')
                    tree = ast.parse(content, filename=str(file_path))
                    visitor = PythonDocVisitor(str(file_path.relative_to(project_path)))
                    visitor.visit(tree)
                    gaps.extend(visitor.gaps)
                except Exception as err:
                    gaps.append({
                        "file": str(file_path.relative_to(project_path)),
                        "line": 1,
                        "symbol": "syntax",
                        "kind": "error",
                        "message": f"Failed to parse AST: {err}"
                    })
    return gaps

def audit_doxygen_gaps(engine: DoxygenQueryEngine, project_path: Path) -> List[Dict[str, Any]]:
    """Scan Doxygen index for documented symbols missing details."""
    gaps = []
    classes = engine.list_all_symbols(kind_filter="class")
    for cls in classes:
        details = engine.query_symbol(cls)
        if not details or "error" in details:
            continue
        if not details.get("brief") and not details.get("detailed"):
            gaps.append({
                "file": details.get("location", {}).get("file", "unknown"),
                "line": int(details.get("location", {}).get("line", 1)),
                "symbol": cls,
                "kind": "class",
                "message": f"Class '{cls}' is missing documentation"
            })
        for member in details.get("members", []):
            if not member.get("brief"):
                gaps.append({
                    "file": member.get("location", {}).get("file", "unknown"),
                    "line": int(member.get("location", {}).get("line", 1)),
                    "symbol": f"{cls}::{member['name']}",
                    "kind": member.get("kind", "member"),
                    "message": f"Member '{cls}::{member['name']}' is missing documentation"
                })
    return gaps

def find_nm_tool() -> Optional[str]:
    """Find the nm tool in PATH or config."""
    env_nm = os.environ.get("DOXYGEN_NM_PATH")
    if env_nm:
        if os.path.exists(env_nm) and os.access(env_nm, os.X_OK):
            return env_nm
        return None
    for name in ["xtensa-esp32-elf-nm", "llvm-nm", "nm"]:
        path = shutil.which(name)
        if path:
            return path
    return None

def find_build_dir(project_path: Path) -> Optional[Path]:
    """Locate build output folders recursively."""
    env_dir = os.environ.get("DOXYGEN_BUILD_DIR")
    if env_dir:
        path = Path(env_dir)
        if not path.is_absolute():
            path = project_path / path
        if path.exists() and path.is_dir():
            return path
        return None
    for candidate in ["build", "bin", "obj", ".pio/build"]:
        path = project_path / candidate
        if path.exists() and path.is_dir():
            return path
    for root, dirs, _ in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', '.git', 'venv'}]
        for d in dirs:
            if d in {'build', 'bin', 'obj'}:
                return Path(root) / d
    return None

def scan_binary_gaps(nm_tool: str, build_dir: Path) -> Dict[str, List[str]]:
    """Scan build object files for undefined symbols."""
    gaps = {}
    obj_files = list(build_dir.rglob("*.o")) + list(build_dir.rglob("*.obj"))
    for obj in obj_files[:50]:  # Limit file count for performance
        try:
            res = subprocess.run(
                [nm_tool, "-u", str(obj)],
                capture_output=True,
                text=True,
                check=True
            )
            undefined = []
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if parts:
                    sym = parts[-1]
                    if not sym.startswith('__') and not sym.startswith('_Z4') and not sym.startswith('_Z3'):
                        undefined.append(sym)
            if undefined:
                rel_path = obj.relative_to(build_dir)
                source_guess = rel_path.with_suffix("")
                gaps[str(source_guess)] = undefined
        except Exception:
            pass
    return gaps

def check_doxygen_parity(engine: DoxygenQueryEngine) -> List[Dict[str, Any]]:
    """Scan Doxygen XML files for documentation-to-code parity mismatches."""
    mismatches = []
    
    for name, info in engine.compounds.items():
        refid = info["refid"]
        xml_file = engine.xml_dir / f"{refid}.xml"
        if not xml_file.exists():
            continue
            
        try:
            tree = ET.parse(xml_file)
            xml_root = tree.getroot()
            if xml_root is None:
                continue
            compounddef = xml_root.find("compounddef")
            if compounddef is None:
                continue
                
            for section in compounddef.findall("sectiondef"):
                for member in section.findall("memberdef"):
                    if member.get("kind") != "function":
                        continue
                        
                    mem_name_elem = member.find("name")
                    mem_name = mem_name_elem.text if mem_name_elem is not None else "unknown"
                    
                    loc_elem = member.find("location")
                    loc_file = loc_elem.get("file") if loc_elem is not None else "unknown"
                    loc_line = int(loc_elem.get("line") or 1) if loc_elem is not None else 1
                    
                    # 1. Extract actual parameters
                    actual_params = []
                    for param in member.findall("param"):
                        declname = param.find("declname")
                        defname = param.find("defname")
                        p_name = None
                        if declname is not None and declname.text:
                            p_name = declname.text
                        elif defname is not None and defname.text:
                            p_name = defname.text
                        if p_name and p_name not in ("self", "cls"):
                            actual_params.append(p_name)
                            
                    # 2. Extract documented parameters
                    comment_params = []
                    detaileddesc = member.find("detaileddescription")
                    if detaileddesc is not None:
                        for paramlist in detaileddesc.findall(".//parameterlist"):
                            if paramlist.get("kind") == "param":
                                for paramitem in paramlist.findall("parameteritem"):
                                    namelist = paramitem.find("parameternamelist")
                                    if namelist is not None:
                                        for name_node in namelist.findall("parametername"):
                                            if name_node.text:
                                                comment_params.append(name_node.text.strip())
                                                
                    if not comment_params and not actual_params:
                        continue
                        
                    # Check for mismatches and redundant
                    for cp in comment_params:
                        if cp not in actual_params:
                            normalized_cp = cp.lower().replace("_", "").replace("-", "")
                            matched_actual = None
                            for ap in actual_params:
                                normalized_ap = ap.lower().replace("_", "").replace("-", "")
                                if normalized_cp == normalized_ap:
                                    matched_actual = ap
                                    break
                                    
                            if matched_actual:
                                mismatches.append({
                                    "file": loc_file,
                                    "line": loc_line,
                                    "symbol": f"{name}::{mem_name}",
                                    "kind": "parameter_mismatch",
                                    "message": f"Parameter name mismatch: documented as '@param {cp}' but signature is '{matched_actual}'"
                                })
                            else:
                                mismatches.append({
                                    "file": loc_file,
                                    "line": loc_line,
                                    "symbol": f"{name}::{mem_name}",
                                    "kind": "parameter_redundant",
                                    "message": f"Redundant parameter documentation: '@param {cp}' does not exist in function signature"
                                })
                                
                    # Check for missing param documentation
                    if comment_params:
                        for ap in actual_params:
                            is_documented = False
                            for cp in comment_params:
                                if cp == ap or cp.lower().replace("_", "").replace("-", "") == ap.lower().replace("_", "").replace("-", ""):
                                    is_documented = True
                                    break
                            if not is_documented:
                                mismatches.append({
                                    "file": loc_file,
                                    "line": loc_line,
                                    "symbol": f"{name}::{mem_name}",
                                    "kind": "parameter_missing",
                                    "message": f"Missing parameter documentation: parameter '{ap}' is in signature but not documented"
                                })
        except Exception:
            pass
            
    return mismatches

