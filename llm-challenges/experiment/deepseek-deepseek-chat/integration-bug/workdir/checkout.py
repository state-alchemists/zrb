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
    # Atomically reserve inventory BEFORE charging.
    # This eliminates the TOCTOU race between check_stock and decrement,
    # preventing both overselling and ghost charges.
    reserved = await inventory.try_decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reserved stock.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock restored")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
