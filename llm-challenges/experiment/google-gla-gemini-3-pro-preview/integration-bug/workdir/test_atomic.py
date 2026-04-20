import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    async def dec(name):
        res = await inv.decrement(1)
        print(f"{name}: {res}")
    await asyncio.gather(dec("A"), dec("B"), dec("C"))

asyncio.run(test())
