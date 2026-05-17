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
    # Reserve stock first to prevent overselling and ghost charges
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    try:
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            # Release reserved stock on payment failure
            await inventory.increment(quantity)
            return False
    except Exception:
        # Ensure stock is released if an unexpected error occurs during payment
        await inventory.increment(quantity)
        raise

    print(f"Order {order_id}: SUCCESS")
    return True
