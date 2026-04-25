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
    # Reserve inventory FIRST (atomic check-and-decrement)
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Now charge - if this fails, we MUST release the reservation
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Release the reserved inventory so others can use it
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed (inventory released)")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
