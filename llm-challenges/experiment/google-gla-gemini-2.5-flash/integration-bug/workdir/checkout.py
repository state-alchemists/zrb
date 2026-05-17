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
    if not await inventory.reserve_stock(quantity):
        print(f"Order {order_id}: out of stock or reservation failed")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        await inventory.release_stock(quantity)  # Rollback inventory
        print(f"Order {order_id}: payment failed, inventory rolled back")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
