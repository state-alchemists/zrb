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
    # Atomically reserve stock — eliminates the TOCTOU race between
    # checking availability and decrementing.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation so another order can
        # use the stock.
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed, stock released")
        return False

    # Reservation + charge both succeeded — item is delivered.
    print(f"Order {order_id}: SUCCESS")
    return True
