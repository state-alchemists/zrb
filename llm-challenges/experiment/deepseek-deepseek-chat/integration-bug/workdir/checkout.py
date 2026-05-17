from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Step 1: Atomically reserve inventory (check + decrement in one critical section).
    # If this fails we're done — no charge, no harm.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Charge the customer.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — restore the reserved stock.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock restored")
        return False

    # Both succeeded. Inventory was already decremented atomically in step 1.
    print(f"Order {order_id}: SUCCESS")
    return True
