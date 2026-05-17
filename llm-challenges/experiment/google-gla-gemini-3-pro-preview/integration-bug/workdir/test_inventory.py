import asyncio
from inventory import Inventory

async def main():
    inventory = Inventory(5)
    
    async def decrement_and_print(i):
        ok = await inventory.decrement(1)
        print(f"{i}: {ok}")

    await asyncio.gather(*(decrement_and_print(i) for i in range(12)))
    print("Final stock:", inventory.stock)

asyncio.run(main())
