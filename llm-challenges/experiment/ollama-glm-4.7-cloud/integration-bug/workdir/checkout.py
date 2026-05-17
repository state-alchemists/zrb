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
    # Check if already charged to prevent duplicate charges
    if await gateway.has_charged(order_id):
        print(f"Order {order_id}: already charged, skipping")
        return False

    # Atomically reserve inventory (prevents overselling)
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Compensation: release reserved inventory
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
