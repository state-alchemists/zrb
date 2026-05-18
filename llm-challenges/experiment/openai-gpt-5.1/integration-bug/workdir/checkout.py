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
    # Optimistic check – real enforcement happens in decrement, which is atomic.
    available = await inventory.check_stock(quantity)
    if not available:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        return False

    decremented = await inventory.decrement(quantity)
    if not decremented:
        # Compensate: refund if we charged but couldn't decrement stock
        # (Should not normally happen under correct locking)
        await gateway.refund(order_id, quantity * price)
        print(f"Order {order_id}: inventory error after payment — refund issued")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
