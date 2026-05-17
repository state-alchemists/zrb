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
    async with inventory.lock:
        if inventory.stock < quantity:
            print(f"Order {order_id}: out of stock")
            return False
        # Reserve inventory immediately (atomically within lock)
        await inventory.decrement(quantity)

    # Now attempt payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed - restore reserved inventory
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
