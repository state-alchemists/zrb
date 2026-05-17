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
    # First, reserve inventory atomically
    reserved = await inventory.reserve_stock(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Then, charge the customer (idempotent to prevent duplicates)
    charged = await gateway.charge_once(order_id, quantity * price)
    if not charged:
        # Charge failed, release reserved inventory
        await inventory.cancel_reservation(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Success - order delivered
    print(f"Order {order_id}: SUCCESS")
    return True
