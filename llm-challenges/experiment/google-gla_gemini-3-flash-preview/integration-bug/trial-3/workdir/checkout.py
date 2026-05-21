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
    # Step 1: Atomically reserve stock (check + decrement, no TOCTOU).
    # Stock is secured before any payment happens.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Try to charge — stock is already held.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Charge failed — release the reserved stock for other customers.
        await inventory.restore(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Step 3: Charge succeeded, reservation is implicitly committed.
    print(f"Order {order_id}: SUCCESS")
    return True
