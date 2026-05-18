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
    # 1. Reserve stock
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # 2. Charge customer
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed, rolling back inventory")
        # 2a. Rollback if charge fails
        await inventory.increment(quantity)
        return False

    # 3. Success
    print(f"Order {order_id}: SUCCESS")
    return True
