from module.auth.migrate import migrate_auth
from module.log.migrate import migrate_log
import asyncio


async def migrate():
    await migrate_auth()
    await migrate_log()


if __name__ == '__main__':
    asyncio.run(migrate())
