import asyncio
from inventory import Inventory

async def test():
    inv = Inventory(1)
    async def chk_and_dec(name):
        print(f"{name} checking")
        res1 = await inv.check_stock(1)
        print(f"{name} check: {res1}")
        if res1:
            res2 = await inv.decrement(1)
            print(f"{name} dec: {res2}")
        
    await asyncio.gather(chk_and_dec("A"), chk_and_dec("B"), chk_and_dec("C"))
    print("Stock:", inv.stock)

asyncio.run(test())
