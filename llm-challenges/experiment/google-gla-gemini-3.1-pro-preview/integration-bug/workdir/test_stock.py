import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    async def chk_and_dec():
        if await inv.check_stock(1):
            return await inv.decrement(1)
        return False
    
    res = await asyncio.gather(*[chk_and_dec() for _ in range(10)])
    print(inv.stock, res)

asyncio.run(test())
