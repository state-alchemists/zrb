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
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Process payment only after inventory is reserved
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # CRITICAL: Release the reserved inventory since payment failed
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # At this point: inventory is decremented and payment succeeded
    # Both are guaranteed to be in sync (1 item per successful charge)
    print(f"Order {order_id}: SUCCESS")
    return True
