import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0.0) # Always succeed
    
    # Send 3 concurrent checkouts for the SAME order_id
    orders = [
        checkout("order_X", 1, 100.0, inventory, gateway)
        for _ in range(3)
    ]
    await asyncio.gather(*orders)
    
    print("Charges:", gateway.charges)
    print("Stock:", inventory.stock)

asyncio.run(main())
