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
    # Atomically reserve inventory. If it fails, we're out of stock.
    if not await inventory.reserve(quantity):
        print(f"Order {order_id}: out of stock")
        return False

    # Charge the customer. If it fails, release the reserved stock.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed, releasing stock")
        await inventory.release(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
