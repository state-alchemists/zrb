from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Reserve stock first (atomic check-and-decrement) to prevent overselling.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed: release reservation.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # At this point: exactly one reservation consumed, and (idempotent) charge recorded.
    print(f"Order {order_id}: SUCCESS")
    return True
