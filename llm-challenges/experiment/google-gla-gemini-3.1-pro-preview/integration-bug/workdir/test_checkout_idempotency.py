import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0.0)
    
    # Concurrent identical orders
    results = await asyncio.gather(
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway)
    )
    
    print("Results:", results)
    print("Stock:", inventory.stock)
    print("Charges:", gateway.charges)

asyncio.run(main())
