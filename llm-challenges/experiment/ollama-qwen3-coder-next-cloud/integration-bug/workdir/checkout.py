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
    # First reserve inventory (atomic operation prevents race conditions)
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Then attempt payment (idempotent - won't charge twice for same order_id)
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed or already processed - restore inventory
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed or duplicate")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
