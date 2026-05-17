import asyncio
from inventory import Inventory

async def hammer():
    inv = Inventory(5)
    async def dec():
        await inv.decrement(1)
    await asyncio.gather(*[dec() for _ in range(20)])
    print(inv.stock)

asyncio.run(hammer())
