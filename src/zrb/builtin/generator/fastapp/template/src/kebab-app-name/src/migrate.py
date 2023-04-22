from module.auth.migrate import migrate_auth
import asyncio


async def migrate():
    await migrate_auth()


if __name__ == '__main__':
    asyncio.run(migrate())
