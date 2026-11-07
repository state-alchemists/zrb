"""The file tools, and the schema name each one answers to.

`zrb.llm.tool` resolves these names lazily; importing this package loads every
file tool at once, which is what the single module it replaced already did.
"""

from zrb.llm.tool.file.analyze import analyze_file
from zrb.llm.tool.file.edit import replace_in_file
from zrb.llm.tool.file.listing import DEFAULT_EXCLUDED_PATTERNS, glob_files, list_files
from zrb.llm.tool.file.mv import move_file
from zrb.llm.tool.file.read import read_file
from zrb.llm.tool.file.rm import remove_file
from zrb.llm.tool.file.search import search_files
from zrb.llm.tool.file.write import write_file

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
