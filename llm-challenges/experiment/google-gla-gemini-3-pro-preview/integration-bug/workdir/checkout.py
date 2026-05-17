import asyncio
from inventory import Inventory
from payments import PaymentGateway

_processed_orders = set()
_processing_orders = set()
_global_lock = asyncio.Lock()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    async with _global_lock:
        if order_id in _processed_orders:
            # If already successfully processed, we don't need to do anything, 
            # but returning True means "this order is paid and successful".
            return True
        if order_id in _processing_orders:
            # Concurrent processing of the exact same order id. 
            # Returning False means "didn't succeed now, it's being handled".
            return False
        _processing_orders.add(order_id)

    try:
        # 1. Reserve inventory to prevent overselling
        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        # 2. Process payment
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            # 3. Rollback inventory if payment fails to avoid ghost items
            await inventory.increment(quantity)
            return False

        # Mark as successfully processed
        async with _global_lock:
            _processed_orders.add(order_id)
            
        print(f"Order {order_id}: SUCCESS")
        return True
    finally:
        async with _global_lock:
            _processing_orders.discard(order_id)
