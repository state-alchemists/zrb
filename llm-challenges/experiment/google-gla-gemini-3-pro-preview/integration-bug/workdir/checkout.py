import asyncio
from inventory import Inventory
from payments import PaymentGateway

_order_locks = {}
_processed_orders = set()
_global_lock = asyncio.Lock()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    async with _global_lock:
        if order_id not in _order_locks:
            _order_locks[order_id] = asyncio.Lock()
        lock = _order_locks[order_id]

    async with lock:
        if order_id in _processed_orders:
            print(f"Order {order_id}: already processed")
            return False

        # Instead of check_stock -> charge -> decrement, we should:
        # decremented = await inventory.decrement(quantity)
        # if not decremented: return False
        # charged = await gateway.charge(...)
        # if not charged: await inventory.increment(quantity); return False

        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            await inventory.increment(quantity)
            return False

        _processed_orders.add(order_id)
        
        async with _global_lock:
            if order_id in _order_locks:
                del _order_locks[order_id]

        print(f"Order {order_id}: SUCCESS")
        return True
