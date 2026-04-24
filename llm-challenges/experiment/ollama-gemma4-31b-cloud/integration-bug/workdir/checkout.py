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
    # Step 1: Reserve stock first (atomic decrement)
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(f"Order {order_id}: out of stock")
        return False

    try:
        # Step 2: Attempt to charge the user
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            # Refund the reserved stock if payment fails
            await inventory.increment(quantity)
            return False

        print(f"Order {order_id}: SUCCESS")
        return True
    except Exception as e:
        # Handle unexpected errors during payment to avoid ghost charges or lost stock
        print(f"Order {order_id}: unexpected error {e}")
        await inventory.increment(quantity)
        return False
