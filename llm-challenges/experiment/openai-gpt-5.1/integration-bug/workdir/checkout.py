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
    # Reserve stock atomically with respect to other orders
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Roll back the reservation so inventory never goes below what is paid for
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed — reservation released")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
