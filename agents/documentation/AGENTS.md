# Documentation Agent - AGENTS.md

> Agent configuration for documentation-related tasks in ZRB project.

---

## 🎯 Purpose

This agent specializes in creating, updating, and maintaining project documentation including:
- README files
- API documentation
- Code comments and docstrings
- Architecture diagrams
- User guides
- Changelog

---

## 🔧 Tools & Capabilities

### Primary Tools

```python
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file
from zrb.llm.tool.web import fetch_url
```

### Available Actions

1. **analyze_code**: Analyze source code structure and generate documentation
2. **write_file**: Write or update documentation files
3. **read_file**: Read existing documentation for reference
4. **bash**: Execute commands (e.g., generate diagrams)

---

## 📋 Documentation Tasks

### 1. Generate README

Generate comprehensive README.md for a module or project.

**Prompt Template:**
```
Analyze the codebase in {target_dir} and generate a comprehensive README.md that includes:
- Project overview and purpose
- Installation instructions
- Quick start guide
- API documentation (if applicable)
- Configuration options
- Examples
- Contributing guidelines

Write the README to {target_dir}/README.md
```

**Example Task:**
```python
from zrb import LLMTask, StrInput
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

generate_readme = LLMTask(
    name="generate-readme",
    description="Generate README.md for a project",
    input=[
        StrInput(name="target_dir", default="./"),
        StrInput(name="project_name", default="My Project"),
    ],
    message="""
    Analyze the codebase in {ctx.input.target_dir} and create a comprehensive README.md.
    
    Project name: {ctx.input.project_name}
    
    Include:
    1. Project description based on code analysis
    2. Installation steps (detect package manager from files)
    3. Usage examples
    4. API documentation if it's a library
    5. Configuration options
    6. License information
    
    Write the output to {ctx.input.target_dir}/README.md
    """,
    tools=[analyze_code, write_file],
)
```

### 2. Generate API Documentation

Generate API docs from code docstrings.

**Prompt Template:**
```
Read all Python files in {src_dir} and generate API documentation.
For each public class and function:
- Extract docstrings
- Document parameters with types
- Document return types
- Provide usage examples

Format as Markdown and save to {output_dir}/api.md
```

### 3. Update Changelog

Maintain changelog based on git history.

**Prompt Template:**
```
Analyze git log since {since_version} and update CHANGELOG.md following Keep a Changelog format.
Categorize changes into:
- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security
```

### 4. Code Documentation

Add docstrings to undocumented code.

**Prompt Template:**
```
Read {file_path} and add comprehensive docstrings to all:
- Modules
- Classes
- Public methods
- Functions

Follow Google docstring style. Update the file in place.
```

---

## 📝 Documentation Standards

### README Structure

```markdown
# Project Name

> One-line description

## 🚀 Quick Start

## 📦 Installation

## 🔧 Configuration

## 📖 Usage

## 🧪 Examples

## 🤝 Contributing

## 📄 License
```

### Docstring Format (Google Style)

```python
def function_name(param1: str, param2: int) -> bool:
    """Short description.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When input is invalid
        
    Example:
        >>> function_name("test", 42)
        True
    """
```

---

## 🎨 Diagram Generation

Use Mermaid for diagrams:

```python
from zrb import LLMTask, CmdTask, StrInput

# Task to generate Mermaid diagram
generate_diagram = LLMTask(
    name="generate-architecture-diagram",
    description="Generate architecture diagram",
    input=[StrInput(name="dir", default="./src")],
    message="""
    Analyze the codebase in {ctx.input.dir} and create a Mermaid diagram
    showing the architecture. Save to architecture.mmd
    """,
    tools=[analyze_code, write_file],
)

# Task to convert to PNG
convert_diagram = CmdTask(
    name="convert-diagram",
    description="Convert Mermaid to PNG",
    input=[StrInput(name="file", default="architecture")],
    cmd="mmdc -i '{ctx.input.file}.mmd' -o '{ctx.input.file}.png'",
)

# Chain tasks
generate_diagram >> convert_diagram
```

---

## ✅ Quality Checklist

Before finalizing documentation:

- [ ] All public APIs are documented
- [ ] Code examples are tested and working
- [ ] Links are valid
- [ ] Screenshots/images are up to date
- [ ] No spelling/grammar errors
- [ ] Follows project style guide

---

## 🔗 Related Agents

- `../planning/AGENTS.md` - For project planning documentation
- `../testing/AGENTS.md` - For test documentation
- `../refactoring/AGENTS.md` - For refactoring documentation

---

*Last updated: 2026-02-02*
