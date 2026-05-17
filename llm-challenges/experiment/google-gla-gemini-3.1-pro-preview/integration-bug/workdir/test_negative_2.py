import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout
import sys

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway()
    orders = [checkout(f"o_{i}", 1, 100, inventory, gateway) for i in range(100)]
    await asyncio.gather(*orders)
    if inventory.stock < 0:
        print("NEGATIVE")
        sys.exit(1)
asyncio.run(main())
