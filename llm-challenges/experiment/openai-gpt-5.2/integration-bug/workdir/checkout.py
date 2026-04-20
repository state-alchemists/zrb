from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Reserve first to prevent overselling under concurrency.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed: rollback reservation so others can buy.
        await inventory.release_reservation(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Payment succeeded and we have reserved stock -> item delivered.
    await inventory.confirm_reservation(quantity)
    print(f"Order {order_id}: SUCCESS")
    return True
