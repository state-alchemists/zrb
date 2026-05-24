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
    # Atomic reserve: check stock and decrement in one step (no await between check and mutation).
    # Eliminates the TOCTOU window that caused overselling and ghost charges.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed — releasing reservation")
        await inventory.release(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
