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
    # Reserve inventory first (atomic check-and-decrement)
    reserved = await inventory.decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Now charge the customer
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Charge failed - restore stock and exit
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
