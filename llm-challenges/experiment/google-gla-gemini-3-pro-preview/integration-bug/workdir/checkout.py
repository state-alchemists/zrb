import asyncio
from inventory import Inventory
from payments import PaymentGateway

# Track global completion to prevent duplicate processing of the exact same order
_completed_orders = set()
_processing_orders = set()

# Lock to ensure inventory operations are atomic across requests
_inventory_lock = asyncio.Lock()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    if order_id in _completed_orders or order_id in _processing_orders:
        return False
        
    _processing_orders.add(order_id)
    try:
        # Check if already charged to prevent double charging for the same order
        if any(c["order_id"] == order_id for c in gateway.charges):
            return False
            
        # 1. Reserve stock first, securely locking the inventory check & decrement
        async with _inventory_lock:
            decremented = await inventory.decrement(quantity)
            
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        # 2. Attempt to charge
        try:
            charged = await gateway.charge(order_id, quantity * price)
        except Exception:
            # Revert reservation if charge process fails unexpectedly
            async with _inventory_lock:
                await inventory.increment(quantity)
            raise
            
        if not charged:
            print(f"Order {order_id}: payment failed, refunding stock")
            async with _inventory_lock:
                await inventory.increment(quantity)
            return False

        print(f"Order {order_id}: SUCCESS")
        _completed_orders.add(order_id)
        return True
    finally:
        _processing_orders.remove(order_id)
