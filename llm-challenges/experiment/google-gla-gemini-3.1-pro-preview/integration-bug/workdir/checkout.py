import asyncio
from inventory import Inventory
from payments import PaymentGateway

_locks = set()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    for charge in gateway.charges:
        if charge["order_id"] == order_id:
            return True

    while order_id in _locks:
        await asyncio.sleep(0.01)

    for charge in gateway.charges:
        if charge["order_id"] == order_id:
            return True

    _locks.add(order_id)
    try:
        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            await inventory.increment(quantity)
            print(f"Order {order_id}: payment failed")
            return False

        print(f"Order {order_id}: SUCCESS")
        return True
    finally:
        _locks.remove(order_id)
