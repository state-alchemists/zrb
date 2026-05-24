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
    # Check if order has already been processed
    if await gateway.is_order_processed(order_id):
        print(f"Order {order_id}: already processed")
        return False

    # Check stock and decrement atomically
    decremented = await inventory.decrement_atomically(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    # Proceed to charge
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Revert decrement if charge fails
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
