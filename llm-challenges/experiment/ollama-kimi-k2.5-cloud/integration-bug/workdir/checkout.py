import asyncio
from inventory import Inventory
from payments import PaymentGateway


# Global lock for checkout sequencing - ensures inventory check/decrement is atomic
_checkout_lock = asyncio.Lock()


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    async with _checkout_lock:
        # First, atomically decrement inventory (reserve the item)
        reserved = await inventory.decrement(quantity)
        if not reserved:
            print(f"Order {order_id}: out of stock")
            return False

    # Charge payment after inventory is reserved
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Refund the inventory reservation since payment failed
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
