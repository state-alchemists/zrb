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
    # First reserve stock atomically - this prevents overselling
    reserved = await inventory.reserve_and_decrement(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Then charge - using charge_once to prevent duplicate charges
    charged = await gateway.charge_once(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        # Rollback the inventory reservation since payment failed
        await inventory.increment(quantity)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
