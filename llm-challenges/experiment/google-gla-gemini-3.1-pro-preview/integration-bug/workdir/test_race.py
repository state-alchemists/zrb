import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    async def dec():
        return await inv.decrement(1)
    
    res = await asyncio.gather(*[dec() for _ in range(10)])
    print(inv.stock, res)

asyncio.run(test())
