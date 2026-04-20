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
    # Atomically reserve inventory first to prevent overselling
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Try to charge the customer
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed or duplicate; release reserved stock
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # At this point, inventory has been decremented exactly once and payment succeeded
    print(f"Order {order_id}: SUCCESS")
    return True
