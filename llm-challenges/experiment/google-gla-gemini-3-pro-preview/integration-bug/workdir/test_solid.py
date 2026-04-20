import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inventory = Inventory(10)
    gateway = PaymentGateway(failure_rate=0)
    
    # 5 concurrent checkouts for same order
    orders = [
        checkout("order_X", 1, 100.0, inventory, gateway)
        for i in range(5)
    ]
    results = await asyncio.gather(*orders)
    print("Results:", results)
    print("Charges:", gateway.charges)
    print("Stock:", inventory.stock)

if __name__ == "__main__":
    asyncio.run(main())
