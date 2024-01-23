import asyncio

from module.auth.migrate import migrate_auth
from module.log.migrate import migrate_log


async def migrate():
    await migrate_auth()
    await migrate_log()


if __name__ == "__main__":
    asyncio.run(migrate())
