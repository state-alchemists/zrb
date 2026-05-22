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
    # Phase 1: Reserve inventory atomically (check + decrement, no TOCTOU gap).
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Phase 2: Charge only after inventory is secured.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reserved stock back.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock released")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
