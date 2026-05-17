import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def test():
    inventory = Inventory(10)
    gateway = PaymentGateway(failure_rate=0)
    
    # Concurrent checkouts for the SAME order_id
    await asyncio.gather(
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway)
    )
    
    print(gateway.charges)

asyncio.run(test())
