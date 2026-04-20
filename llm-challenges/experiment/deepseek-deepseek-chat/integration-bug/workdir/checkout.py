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
    # Atomically reserve inventory
    reserved = await inventory.reserve_and_decrement(order_id, quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        # Release the reserved inventory since payment failed
        await inventory.release_reservation(order_id)
        return False

    # If payment succeeded, the reservation is already counted as decremented
    print(f"Order {order_id}: SUCCESS")
    return True
