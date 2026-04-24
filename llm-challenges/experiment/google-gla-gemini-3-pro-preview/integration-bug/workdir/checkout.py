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
    available = await inventory.check_stock(quantity)
    if not available:
        print(f"Order {order_id}: out of stock")
        return False

    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock (concurrent)")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        await inventory.increment(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
