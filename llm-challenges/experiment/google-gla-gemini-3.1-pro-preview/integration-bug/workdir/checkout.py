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
    # 1. Reserve inventory
    if not await inventory.decrement(quantity):
        print(f"Order {order_id}: out of stock")
        return False

    # 2. Charge payment
    charged = False
    try:
        charged = await gateway.charge(order_id, quantity * price)
    finally:
        # 3. Rollback reservation if payment failed or raised an exception
        if not charged:
            await inventory.increment(quantity)

    if not charged:
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
