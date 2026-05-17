import asyncio
from inventory import Inventory
from payments import PaymentGateway

_processed_orders = set()
_order_locks = {}

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    if order_id not in _order_locks:
        _order_locks[order_id] = asyncio.Lock()
        
    async with _order_locks[order_id]:
        if order_id in _processed_orders:
            print(f"Order {order_id}: already processed")
            return True

        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            # Rollback inventory if payment fails
            await inventory.increment(quantity)
            return False

        _processed_orders.add(order_id)
        print(f"Order {order_id}: SUCCESS")
        return True
