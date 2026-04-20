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
    async with inventory._lock:
        available = await inventory.check_stock(quantity)
        if not available:
            print(f"Order {order_id}: out of stock")
            return False
        
        # Decrement stock inside the lock to reserve the item
        decremented = await inventory.decrement(quantity)
        if not decremented:
            # This case should ideally not happen if check_stock is reliable,
            # but it's a safeguard.
            print(f"Order {order_id}: inventory error during decrement (should not happen)")
            return False

    # Attempt payment outside the inventory lock to avoid holding it too long
    charged = await gateway.charge(order_id, quantity * price)

    if not charged:
        print(f"Order {order_id}: payment failed, re-incrementing stock")
        async with inventory._lock: # Re-acquire lock to increment stock safely
            await inventory.increment(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
