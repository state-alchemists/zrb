import aiofiles


async def read_text_file(filename: str) -> str:
    async with aiofiles.open(filename, mode='r') as file:
        content = await file.read()
    return content


async def write_text_file(filename: str, content: str):
    async with aiofiles.open(filename, mode='w') as file:
        await file.write(content)
