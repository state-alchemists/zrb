from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Reserve inventory first (atomic check-and-decrement).
    # This eliminates the TOCTOU race between check_stock and decrement.
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Now attempt payment. The item is already reserved — no way to
    # charge without a corresponding item to deliver.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation back to inventory.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, inventory released")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
