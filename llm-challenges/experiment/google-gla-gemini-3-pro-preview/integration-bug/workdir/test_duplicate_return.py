import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(0.0)
    
    orders = [
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_1", 1, 100.0, inventory, gateway)
    ]
    results = await asyncio.gather(*orders)
    print("Results:", results)
    print("Charges:", gateway.charges)

asyncio.run(main())
