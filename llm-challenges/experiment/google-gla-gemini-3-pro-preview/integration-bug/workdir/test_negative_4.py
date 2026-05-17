import asyncio
from inventory import Inventory

async def hammer():
    inv = Inventory(5)
    async def dec():
        if await inv.check_stock(1):
            await inv.decrement(1)
    await asyncio.gather(*[dec() for _ in range(10)])
    print(inv.stock)

asyncio.run(hammer())
