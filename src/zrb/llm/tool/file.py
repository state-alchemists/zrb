from zrb.llm.tool.file_analyze import analyze_file
from zrb.llm.tool.file_edit import replace_in_file
from zrb.llm.tool.file_list import DEFAULT_EXCLUDED_PATTERNS, glob_files, list_files
from zrb.llm.tool.file_read import read_file, read_files
from zrb.llm.tool.file_search import search_files
from zrb.llm.tool.file_write import write_file, write_files

list_files.__name__ = "LS"
glob_files.__name__ = "Glob"
read_file.__name__ = "Read"
read_files.__name__ = "ReadMany"
write_file.__name__ = "Write"
write_files.__name__ = "WriteMany"
replace_in_file.__name__ = "Edit"
search_files.__name__ = "Grep"
analyze_file.__name__ = "AnalyzeFile"

__all__ = [
    "DEFAULT_EXCLUDED_PATTERNS",
    "list_files",
    "glob_files",
    "read_file",
    "read_files",
    "write_file",
    "write_files",
    "replace_in_file",
    "search_files",
    "analyze_file",
]
