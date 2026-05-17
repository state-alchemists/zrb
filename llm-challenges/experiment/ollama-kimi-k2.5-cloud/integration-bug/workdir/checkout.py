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
    # Step 1: Reserve inventory FIRST (atomically check and decrement)
    reserved = await inventory.try_decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Charge payment AFTER inventory is reserved
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # CRITICAL: Release inventory if payment failed to avoid "ghost reservations"
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed — inventory released")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
