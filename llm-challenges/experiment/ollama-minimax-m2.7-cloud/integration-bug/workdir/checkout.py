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
    # Reserve inventory atomically before charging
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge the customer
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reserved inventory
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    # Inventory was already reserved and decremented in reserve(),
    # so no further inventory operation is needed
    print(f"Order {order_id}: SUCCESS")
    return True
