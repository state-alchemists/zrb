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
    # Atomically check stock and decrement
    decremented = await inventory.check_and_decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    # Attempt payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed. Restoring stock.")
        await inventory.increment(quantity)  # Compensating action
        return False

    # If both succeeded, the order is complete
    print(f"Order {order_id}: SUCCESS")
    return True
