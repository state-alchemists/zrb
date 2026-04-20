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
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock or inventory error")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        await inventory.increment(quantity)  # Refund the item to inventory
        print(f"Order {order_id}: payment failed, inventory restored")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
