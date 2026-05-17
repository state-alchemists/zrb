import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    for _ in range(50):
        inventory = Inventory(2)
        gateway = PaymentGateway(failure_rate=0.5)
        
        # 10 orders, 2 duplicate pairs
        orders = [
            checkout(f"order_{i}", 1, 100.0, inventory, gateway)
            for i in range(10)
        ] + [
            checkout("order_1", 1, 100.0, inventory, gateway),
            checkout("order_2", 1, 100.0, inventory, gateway)
        ]
        
        results = await asyncio.gather(*orders)
        
        successful = sum(results)
        items_sold = 2 - inventory.stock
        charge_ids = [c["order_id"] for c in gateway.charges]
        duplicates = len(charge_ids) - len(set(charge_ids))
        
        if inventory.stock < 0:
            print("ERROR: negative inventory")
        if abs(gateway.total_charged - successful * 100.0) > 0.01:
            print("ERROR: ghost charge")
        if duplicates > 0:
            print("ERROR: duplicate charge")
            
    print("Done")

asyncio.run(main())
