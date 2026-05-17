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
    # 1. Reserve stock first to prevent overselling
    # Instead of check_stock -> charge -> decrement (RACE CONDITION)
    # We use decrement immediately to "lock" the stock.
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    try:
        # 2. Attempt payment
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            # Release stock if payment fails
            await inventory.increment(quantity)
            return False
    except Exception as e:
        # Ensure stock is released if an unexpected error occurs during payment
        await inventory.increment(quantity)
        print(f"Order {order_id}: unexpected error during payment: {e}")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
