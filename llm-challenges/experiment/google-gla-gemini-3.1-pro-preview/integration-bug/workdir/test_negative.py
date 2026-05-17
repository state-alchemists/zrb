import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    await asyncio.gather(*[inv.decrement(1) for _ in range(10)])
    print("Stock:", inv.stock)

asyncio.run(test())
