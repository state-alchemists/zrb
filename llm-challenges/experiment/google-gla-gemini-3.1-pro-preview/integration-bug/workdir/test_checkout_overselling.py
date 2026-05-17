import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(1)
    gateway = PaymentGateway(0)
    
    # Same order ID called concurrently
    await asyncio.gather(
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_2", 1, 100, inventory, gateway),
    )
    
    print("Stock:", inventory.stock)
    print("Charges:", gateway.charges)

asyncio.run(main())
