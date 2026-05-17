import asyncio
from inventory import Inventory
from payments import PaymentGateway

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    decremented = await inventory.decrement(quantity)
    if not decremented:
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        await inventory.increment(quantity)
        return False

    return True

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0.5)
    
    orders = [
        checkout(f"order_{i}", 1, 100, inventory, gateway)
        for i in range(12)
    ]
    results = await asyncio.gather(*orders)
    
    successful = sum(results)
    items_sold = 5 - inventory.stock
    print(f"Successful orders:  {successful}")
    print(f"Items sold:         {items_sold}")
    print(f"Remaining stock:    {inventory.stock}")
    print(f"Total charged:      {gateway.total_charged}")

asyncio.run(main())
