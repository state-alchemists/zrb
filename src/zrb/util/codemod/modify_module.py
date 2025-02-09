def prepend_code_to_module(original_code: str, new_code: str) -> str:
    lines = original_code.splitlines()
    last_import_index = -1
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line.startswith("import") or stripped_line.startswith("from"):
            last_import_index = i
        else:
            break
    lines.insert(last_import_index + 1, new_code)
    return "\n".join(lines)
