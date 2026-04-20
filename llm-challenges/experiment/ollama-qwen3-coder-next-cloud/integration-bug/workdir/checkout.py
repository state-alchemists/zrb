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
    # Step 1: Atomically reserve inventory
    reserved = await inventory.try_reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Attempt charge
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Step 3: Release inventory if charge fails
        await inventory.release_reservation(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
