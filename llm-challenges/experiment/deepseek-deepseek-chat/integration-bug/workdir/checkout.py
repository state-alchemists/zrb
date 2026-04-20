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
    # First, atomically reserve the inventory
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Try to charge the payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed, restore the inventory
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Both inventory reservation and payment succeeded
    print(f"Order {order_id}: SUCCESS")
    return True
