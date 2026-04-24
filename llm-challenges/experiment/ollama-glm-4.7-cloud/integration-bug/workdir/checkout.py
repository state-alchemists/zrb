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
    # Reserve stock atomically before charging
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge payment (idempotent - won't charge same order twice)
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed, release the reservation
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Payment succeeded, stock already reserved
    print(f"Order {order_id}: SUCCESS")
    return True
