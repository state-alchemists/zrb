import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def test_duplicate_orders():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0.0)
    
    orders = [
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway)
    ]
    results = await asyncio.gather(*orders)
    
    print("Successes:", sum(results))
    print("Charges:", gateway.charges)

asyncio.run(test_duplicate_orders())
