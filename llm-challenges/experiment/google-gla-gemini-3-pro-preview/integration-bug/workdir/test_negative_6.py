import asyncio
from inventory import Inventory

async def hammer():
    inv = Inventory(5)
    async def dec():
        # wait 0.02
        # if stock >= 1
        #   stock -= 1
        # if everyone starts at same time, all 100 coros pass await sleep, read stock (which is 5 >= 1), and ALL decrement stock.
        # This will result in negative stock.
        await inv.decrement(1)
        
    await asyncio.gather(*[dec() for _ in range(100)])
    print(inv.stock)

asyncio.run(hammer())
