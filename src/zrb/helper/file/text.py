import os

import aiofiles

from zrb.helper.typecheck import typechecked


@typechecked
async def read_text_file_async(file_name: str) -> str:
    async with aiofiles.open(file_name, mode="r") as file:
        content = await file.read()
    return content


@typechecked
async def write_text_file_async(file_name: str, content: str):
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    async with aiofiles.open(file_name, mode="w") as file:
        await file.write(content)


@typechecked
async def append_text_file_async(file_name: str, additional_content: str):
    content = await read_text_file_async(file_name)
    if content != "":
        additional_content = "\n" + additional_content
    new_content = content + additional_content
    await write_text_file_async(file_name, new_content)
