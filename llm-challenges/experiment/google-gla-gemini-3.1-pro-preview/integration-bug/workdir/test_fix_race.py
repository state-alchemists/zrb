import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    results = await asyncio.gather(*[inv.decrement(1) for _ in range(5)])
    print("Decrement results:", results)
    print("Remaining stock:", inv.stock)

asyncio.run(test())
