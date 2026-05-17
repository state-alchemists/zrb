import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    await asyncio.gather(inv.decrement(1), inv.decrement(1))
    print(inv.stock)

asyncio.run(test())
