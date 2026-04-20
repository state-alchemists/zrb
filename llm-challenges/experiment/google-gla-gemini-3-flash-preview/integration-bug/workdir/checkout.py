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
    # Reserve stock first to prevent overselling and ghost charges
    if not await inventory.decrement(quantity):
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        # Release reserved stock if payment fails
        await inventory.increment(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
