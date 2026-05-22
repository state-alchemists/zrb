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
    # Atomic reserve — check and decrement in one shot, no TOCTOU race.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock released")
        return False

    # Stock already decremented by reserve; payment succeeded.
    print(f"Order {order_id}: SUCCESS")
    return True
