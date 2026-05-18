from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Step 1: Atomically reserve inventory
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Charge payment (idempotent - safe to retry)
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Release reserved inventory since payment failed
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Both steps succeeded - inventory already deducted, payment confirmed
    print(f"Order {order_id}: SUCCESS")
    return True
