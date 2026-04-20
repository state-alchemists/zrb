import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0)
    
    # Run two identical checkouts concurrently
    results = await asyncio.gather(
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_1", 1, 100.0, inventory, gateway)
    )
    print("Results:", results)
    print("Charges:", gateway.charges)
    print("Stock:", inventory.stock)

if __name__ == "__main__":
    asyncio.run(main())
