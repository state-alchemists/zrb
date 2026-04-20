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
    # First atomically reserve inventory - prevents race conditions and overselling
    reserved = await inventory.reserve_and_decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Then charge payment - idempotent gateway handles duplicates
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed: restore inventory since we already held it
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
