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
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    try:
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            await inventory.increment(quantity)
            return False
    except Exception as e:
        print(f"Order {order_id}: error during payment — {e}")
        await inventory.increment(quantity)
        raise e

    print(f"Order {order_id}: SUCCESS")
    return True
