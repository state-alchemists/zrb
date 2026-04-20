import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(2)
    # Payment always fails
    gateway = PaymentGateway(failure_rate=1.0)
    
    orders = [
        checkout(f"order_{i}", 1, 100.0, inventory, gateway)
        for i in range(10)
    ]
    await asyncio.gather(*orders)
    
    print("Stock:", inventory.stock)
    
asyncio.run(main())
