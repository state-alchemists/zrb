from zrb.llm.tool.file_analyze import analyze_file
from zrb.llm.tool.file_edit import replace_in_file
from zrb.llm.tool.file_list import DEFAULT_EXCLUDED_PATTERNS, glob_files, list_files
from zrb.llm.tool.file_mv import move_file
from zrb.llm.tool.file_read import read_file
from zrb.llm.tool.file_rm import remove_file
from zrb.llm.tool.file_search import search_files
from zrb.llm.tool.file_write import write_file

list_files.__name__ = "LS"
glob_files.__name__ = "Glob"
read_file.__name__ = "Read"
write_file.__name__ = "Write"
replace_in_file.__name__ = "Edit"
search_files.__name__ = "Grep"
analyze_file.__name__ = "AnalyzeFile"
remove_file.__name__ = "RM"
move_file.__name__ = "MV"

__all__ = [
    "DEFAULT_EXCLUDED_PATTERNS",
    "list_files",
    "glob_files",
    "read_file",
    "write_file",
    "replace_in_file",
    "search_files",
    "analyze_file",
    "remove_file",
    "move_file",
]
