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
    """
    Handles the checkout process atomically.

    1. Reserves inventory.
    2. Charges the customer.
    3. If charging fails, releases the inventory.
    """
    # Atomically reserve inventory
    if not await inventory.reserve(quantity):
        print(f"Order {order_id}: out of stock")
        return False

    # Charge the customer
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed, releasing stock")
        # If charge fails, release the inventory
        await inventory.release(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
