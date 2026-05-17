import asyncio
from inventory import Inventory
from payments import PaymentGateway

_locks = {}
_locks_lock = asyncio.Lock()

async def _get_lock(order_id: str):
    async with _locks_lock:
        if order_id not in _locks:
            _locks[order_id] = asyncio.Lock()
        return _locks[order_id]

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    lock = await _get_lock(order_id)
    async with lock:
        if gateway.has_charged(order_id):
            return True

        available = await inventory.check_stock(quantity)
        if not available:
            print(f"Order {order_id}: out of stock")
            return False

        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            return False

        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: inventory error after payment — item not delivered")
            await gateway.refund(order_id, quantity * price)
            return False

        print(f"Order {order_id}: SUCCESS")
        return True

