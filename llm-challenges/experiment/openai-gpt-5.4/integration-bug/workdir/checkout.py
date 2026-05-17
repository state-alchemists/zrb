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

    charged = await gateway.charge(order_id, quantity * price)
    if charged:
        print(f"Order {order_id}: SUCCESS")
        return True

    await inventory.release(quantity)
    if await gateway.is_charged(order_id):
        print(f"Order {order_id}: already charged")
        return False

    print(f"Order {order_id}: payment failed")
    return False
