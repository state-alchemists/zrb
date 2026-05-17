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
    # Step 1: Atomically reserve inventory before charging
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Charge the customer (idempotent - prevents duplicate charges)
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Rollback: release reserved inventory
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Step 3: Success - inventory already decremented, payment complete
    print(f"Order {order_id}: SUCCESS")
    return True
