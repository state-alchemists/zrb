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
    # Reserve inventory first (atomic check-and-decrement)
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge payment after inventory is reserved
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Release reservation if payment fails
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
