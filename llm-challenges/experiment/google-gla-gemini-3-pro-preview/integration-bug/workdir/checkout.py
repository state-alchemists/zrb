import asyncio
from inventory import Inventory
from payments import PaymentGateway

_lock = asyncio.Lock()
_processing_orders = set()


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # 1. Acquire global lock to prevent race condition in inventory decrement
    #    and handle duplicate order processing
    async with _lock:
        if order_id in _processing_orders:
            print(f"Order {order_id}: already processing")
            return False

        _processing_orders.add(order_id)

        # Check and decrement must be atomic at the checkout level
        # since Inventory itself is not thread-safe/async-safe.
        decremented = await inventory.decrement(quantity)

    if not decremented:
        print(f"Order {order_id}: out of stock")
        async with _lock:
            _processing_orders.remove(order_id)
        return False

    # 2. Charge payment outside the lock
    charged = await gateway.charge(order_id, quantity * price)

    if not charged:
        print(f"Order {order_id}: payment failed")
        # 3. Restore inventory if payment fails
        async with _lock:
            await inventory.increment(quantity)
            _processing_orders.remove(order_id)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
