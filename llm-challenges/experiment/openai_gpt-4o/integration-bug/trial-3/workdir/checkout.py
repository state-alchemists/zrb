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
    # Reserve stock first (atomic check-and-decrement).
    # This eliminates the TOCTOU race between check_stock and decrement.
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Stock is now reserved. Attempt payment.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock released")
        return False

    # Payment succeeded — order fulfilled.
    print(f"Order {order_id}: SUCCESS")
    return True
