import asyncio
from inventory import Inventory
from payments import PaymentGateway

_CHECKOUT_LOCK = asyncio.Lock()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    async with _CHECKOUT_LOCK:
        # Attempt to decrement inventory first. This also acts as a stock check.
        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock or inventory error")
            return False

        # If inventory is reserved, attempt to charge.
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed. Reverting inventory.")
            await inventory.increment(quantity)  # Refund the reserved item
            return False

        print(f"Order {order_id}: SUCCESS")
        return True
