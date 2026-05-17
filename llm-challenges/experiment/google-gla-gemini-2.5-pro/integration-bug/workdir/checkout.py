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
    # Atomically reserve inventory
    if not await inventory.reserve(quantity):
        print(f"Order {order_id}: out of stock")
        return False

    # Charge payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed, releasing inventory")
        await inventory.release(quantity)  # Rollback
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
