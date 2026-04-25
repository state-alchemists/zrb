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
    # Step 1: Atomically reserve inventory (check + decrement in one go).
    # This prevents two concurrent checkouts from overselling.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Attempt payment.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock returned")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
