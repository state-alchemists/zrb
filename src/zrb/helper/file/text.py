import aiofiles


async def read_text_file_async(file_name: str) -> str:
    async with aiofiles.open(file_name, mode='r') as file:
        content = await file.read()
    return content


async def write_text_file_async(file_name: str, content: str):
    async with aiofiles.open(file_name, mode='w') as file:
        await file.write(content)


async def append_text_file_async(file_name: str, additional_content: str):
    content = await read_text_file_async(file_name)
    if content != '':
        additional_content = '\n' + additional_content
    new_content = content + additional_content
    await write_text_file_async(file_name, new_content)
