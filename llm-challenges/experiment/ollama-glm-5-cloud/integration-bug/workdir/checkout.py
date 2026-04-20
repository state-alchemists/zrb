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
    # Step 1: Reserve inventory first (atomic decrement)
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Charge payment (stock is now reserved)
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed - release the reserved stock
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Step 3: Success - item reserved and paid
    print(f"Order {order_id}: SUCCESS")
    return True