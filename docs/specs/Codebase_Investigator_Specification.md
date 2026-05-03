# Codebase Investigator: Operational Spec

## Purpose
`codebase_investigator` sub-agent for deep analysis software project. Goal: structured understanding architecture, dependencies, components. Help bug fix, feature, refactor.

## Operational Flow:

### 1. Input
Agent gets `objective` from main agent. Focus specific codebase aspects (e.g., "analyze server config", "map deps").

```python
# Conceptual input
objective = {
    "task": "analyze_server_configuration",
    "details": "Identify current configuration mechanisms, state management, and IDE integration points for 'doxygen-mcp' server."
}
```

### 2. Codebase Traversal
Traverse directory. Identify relevant files/dirs:
*   Read metadata.
*   Identify extensions.
*   Respect `.gitignore`.

```python
import os
import fnmatch

def traverse_codebase(root_dir, ignore_patterns):
    """
    Conceptual traverse, respect ignore patterns.
    """
    relevant_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if not any(fnmatch.fnmatch(file_path, pattern) for pattern in ignore_patterns):
                relevant_files.append(file_path)
    return relevant_files
```

### 3. Static Analysis
Analyze source without execution:
*   **Dependency Mapping:** Imports, calls, relationships. Build graph.
*   **Architectural Pattern Recognition:** Detect MVC, client-server, etc.
*   **Configuration Analysis:** Locate/parse `.json`, `.yaml`, `.ini`, code configs.
*   **Symbol Extraction:** Functions, classes, variables definitions/usages.
*   **Contextual Understanding:** Code, comments, docs analysis for purpose.

```python
import re

def analyze_python_file(file_path):
    """
    Conceptual static analysis Python file.
    Extract imports, class/function definitions.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    imports = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z0-9_.]+)', content, re.MULTILINE)
    classes = re.findall(r'^\s*class\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
    functions = re.findall(r'^\s*def\s+([a-zA-Z0-9_]+)\s*\(', content, re.MULTILINE)

    config_patterns = re.findall(r'([A-Z_]+)\s*=\s*(.+)', content) 

    return {
        "file": file_path,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "potential_configs": config_patterns
    }
```

### 4. Info Synthesis
Gathered info into coherent model:
*   Prioritize info on request focus.
*   Identify key paths, symbols, insights.
*   Detect mod/improve areas.

```python
def synthesize_report(analysis_data, objective):
    """
    Conceptual synthesize analysis data into report.
    """
    report = {"summary": f"Analysis report for objective: {objective['task']}"}
    config_findings = []
    state_management_findings = []

    for data in analysis_data:
        if "config" in data.get("file", "").lower() or "doxyfile" in data.get("file", "").lower():
            config_findings.append(data)

    report["configuration_details"] = config_findings
    report["potential_ide_integration_points"] = [] 
    report["codebase_state_tracking"] = [] 

    return report
```

### 5. Output
Structured report:
*   Key file paths, relevance.
*   Symbols, definitions, usages.
*   Architectural insights.
*   Actionable recommendations.
*   Answers to objective questions.

```python
def generate_markdown_report(final_report):
    """
    Conceptual format final report Markdown.
    """
    markdown_output = f"# Codebase Investigator Report: {final_report['summary']}\n\n"
    markdown_output += "## Configuration Details\n"
    for config in final_report.get("configuration_details", []):
        markdown_output += f"- File: `{config['file']}`\n"
        markdown_output += f"  Potential Configs: {config.get('potential_configs', 'N/A')}\n"
    return markdown_output
```

## Key Capabilities:
*   **Holistic View:** interaction understanding.
*   **Targeted Analysis:** focus specific aspects.
*   **Pattern Recognition:** engineer patterns/anti-patterns identification.
*   **Dependency Resolution:** internal/external mapping.

## Limitations:
*   Static analysis only. No execution.
*   Proprietary algorithms. Interpret output only.
*   Iterations/specific objectives needed for nuance.
