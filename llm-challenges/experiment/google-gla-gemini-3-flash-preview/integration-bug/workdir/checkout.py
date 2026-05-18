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
    # Try to reserve inventory first to prevent overselling
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    # Attempt payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Refund inventory if payment fails to prevent ghost charges/lost stock
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
