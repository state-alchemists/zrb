import asyncio
from inventory import Inventory

async def main():
    inventory = Inventory(1)
    
    # Simulating the exact scenario of refunding while another checkout is proceeding
    async def process_1():
        print("1 starting")
        res = await inventory.decrement(1)
        print("1 dec:", res)
        await asyncio.sleep(0.05) # "charging"
        print("1 ref:")
        await inventory.increment(1) # "refund"
        
    async def process_2():
        print("2 starting")
        res = await inventory.decrement(1)
        print("2 dec:", res)
        
    await asyncio.gather(process_1(), process_2())
    print("Stock:", inventory.stock)
    
asyncio.run(main())
