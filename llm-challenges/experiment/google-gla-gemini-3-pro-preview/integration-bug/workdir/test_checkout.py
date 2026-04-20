import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(2)
    gateway = PaymentGateway(failure_rate=0)
    
    # Run 5 concurrent checkouts for DIFFERENT orders
    orders = [
        checkout(f"order_{i}", 1, 100.0, inventory, gateway)
        for i in range(5)
    ]
    results = await asyncio.gather(*orders)
    print("Results:", results)
    print("Charges:", gateway.charges)
    print("Stock:", inventory.stock)

if __name__ == "__main__":
    asyncio.run(main())
