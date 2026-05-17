import asyncio
from inventory import Inventory
from payments import PaymentGateway

_processing = set()
_processed = set()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Ensure idempotency and avoid duplicate concurrent processing
    if order_id in _processed or order_id in _processing:
        return False
        
    _processing.add(order_id)
    try:
        # 1. Reserve inventory first to prevent overselling
        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        # 2. Process payment only after securing inventory
        try:
            charged = await gateway.charge(order_id, quantity * price)
        except Exception:
            # Rollback on unexpected error
            await inventory.increment(quantity)
            raise
            
        if not charged:
            print(f"Order {order_id}: payment failed")
            # 3. Rollback inventory if payment fails
            await inventory.increment(quantity)
            return False

        _processed.add(order_id)
        print(f"Order {order_id}: SUCCESS")
        return True
    finally:
        _processing.remove(order_id)
