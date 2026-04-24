from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    already_charged = await gateway.is_charged(order_id)
    if already_charged:
        print(f"Order {order_id}: already processed")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        return False

    # Only after a successful charge do we reserve inventory.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        # We never want a successful charge without delivery.
        # Compensate by refunding.
        await gateway.refund(order_id)
        print(f"Order {order_id}: inventory error after payment — item not delivered")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
