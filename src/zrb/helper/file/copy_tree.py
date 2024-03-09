import fnmatch
import os
import shutil

from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.log import logger
from zrb.helper.string.parse_replacement import parse_replacement
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Iterable, Mapping, Optional


@typechecked
async def copy_tree(
    src: str,
    dst: str,
    replacements: Optional[Mapping[str, str]] = None,
    excludes: Optional[Iterable[str]] = None,
    skip_parsing: Optional[Iterable[str]] = None,
):
    if replacements is None:
        replacements = {}
    if excludes is None:
        excludes = []
    if skip_parsing is None:
        skip_parsing = []
    names = os.listdir(src)
    new_dst = parse_replacement(dst, replacements)
    if not os.path.exists(new_dst):
        os.makedirs(new_dst)
    for name in names:
        src_name = os.path.join(src, name)
        if any(fnmatch.fnmatch(src_name, pattern) for pattern in excludes):
            continue
        dst_name = os.path.join(dst, name)
        if os.path.isdir(src_name):
            await copy_tree(src_name, dst_name, replacements, excludes, skip_parsing)
            continue
        new_dst_name = parse_replacement(dst_name, replacements)
        shutil.copy2(src_name, new_dst_name)
        try:
            if any(fnmatch.fnmatch(new_dst_name, pattern) for pattern in skip_parsing):
                continue
            file_content = await read_text_file_async(new_dst_name)
            new_file_content = parse_replacement(file_content, replacements)
            await write_text_file_async(new_dst_name, new_file_content)
        except Exception:
            logger.error(f"Cannot parse file: {new_dst_name}")
