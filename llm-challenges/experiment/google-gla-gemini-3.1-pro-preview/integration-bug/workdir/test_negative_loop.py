import asyncio
from inventory import Inventory
from payments import PaymentGateway
import checkout as ch

async def run_one():
    inv = Inventory(5)
    gw = PaymentGateway(0.25)
    orders = [ch.checkout(f"order_{i}", 1, 100, inv, gw) for i in range(12)]
    await asyncio.gather(*orders)
    if inv.stock < 0:
        return True
    return False

async def main():
    for _ in range(100):
        if await run_one():
            print("Negative inventory found!")
            return
    print("No negative inventory found.")

asyncio.run(main())
