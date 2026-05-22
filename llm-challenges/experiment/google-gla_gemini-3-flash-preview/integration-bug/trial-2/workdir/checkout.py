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
    # Phase 1: Reserve stock atomically — no await between check and decrement
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Phase 2: Process payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed (reservation released)")
        return False

    # Phase 3: Delivered — stock was already decremented in reserve()
    print(f"Order {order_id}: SUCCESS")
    return True
