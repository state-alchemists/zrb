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
    # Reserve stock atomically first — no overselling
    reserved = await inventory.try_reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Charge after reservation — ghost charge is impossible since stock is already ours
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Roll back the reservation on payment failure
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed — stock released")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
