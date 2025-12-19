import os
import shutil

# Paths
ZRB_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
PROMPT_CONFIG_DIR = os.path.join(ZRB_ROOT, 'src/zrb/config/default_prompt')
PROMPT_PY = os.path.join(ZRB_ROOT, 'src/zrb/task/llm/prompt.py')
ANALYSIS_DIR = os.path.dirname(__file__)

def update_prompt_files():
    print("Updating system prompt files...")
    
    # Update system_prompt.md
    src = os.path.join(ANALYSIS_DIR, 'proposed_system_prompt.md')
    dst = os.path.join(PROMPT_CONFIG_DIR, 'system_prompt.md')
    shutil.copy(src, dst)
    print(f"Updated {dst}")

    # Update interactive_system_prompt.md
    src = os.path.join(ANALYSIS_DIR, 'proposed_interactive_system_prompt.md')
    dst = os.path.join(PROMPT_CONFIG_DIR, 'interactive_system_prompt.md')
    shutil.copy(src, dst)
    print(f"Updated {dst}")

def update_prompt_logic():
    print("Updating prompt.py logic for context injection...")
    
    with open(PROMPT_PY, 'r') as f:
        content = f.read()

    # 1. Add import for finding project root and files
    if "from zrb.util.file import read_dir, read_file_with_line_numbers" in content:
        content = content.replace(
            "from zrb.util.file import read_dir, read_file_with_line_numbers",
            "from zrb.util.file import read_dir, read_file_with_line_numbers, read_file"
        )
    
    # 2. Add helper to get file tree
    file_tree_helper = """
def _get_file_tree_context(cwd: str) -> str:
    # Simple recursive lister or just top-level for now to save tokens
    # In a real implementation, we might want a 'tree' equivalent
    try:
        entries = os.listdir(cwd)
        entries = [e + '/' if os.path.isdir(os.path.join(cwd, e)) else e for e in entries]
        # Filter hidden
        entries = [e for e in entries if not e.startswith('.')]
        return "\n".join(entries[:50]) # Limit to 50 items
    except Exception:
        return "(Unable to list directory)"

def _get_project_rules(cwd: str) -> str:
    # check for ZRB.md or CLAUDE.md
    candidates = ['ZRB.md', 'CLAUDE.md']
    for c in candidates:
        p = os.path.join(cwd, c)
        if os.path.isfile(p):
            return f"\n\nmake_markdown_section('📏 PROJECT RULES ({c})', read_file(p))"
    return ""
"""
    
    # This is a conceptual patch. In reality, we'd use the `replace` tool to insert this carefully.
    # For this script, we just print what needs to be done.
    print("Ready to inject _get_file_tree_context and _get_project_rules into prompt.py")

if __name__ == "__main__":
    update_prompt_files()
    update_prompt_logic()
