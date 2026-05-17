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
    # Reserve inventory atomically
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge payment
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Release reservation since payment failed
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Payment succeeded, order is complete
    print(f"Order {order_id}: SUCCESS")
    return True
