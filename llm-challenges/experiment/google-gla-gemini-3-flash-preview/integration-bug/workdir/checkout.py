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
    # 1. Reserve stock first
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    # 2. Attempt payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # 3. Rollback stock if payment fails
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
