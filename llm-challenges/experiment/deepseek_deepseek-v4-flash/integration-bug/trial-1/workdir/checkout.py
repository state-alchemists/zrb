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
    # Atomically reserve stock — no TOCTOU gap between check and decrement.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge the customer.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation so another order can use it.
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
