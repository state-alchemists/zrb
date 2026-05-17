from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Phase 1: Reserve stock atomically. No other coroutine can reserve over us.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Phase 2: Attempt charge. On failure, release the reservation.
    amount = quantity * price
    charged = await gateway.charge(order_id, amount)
    if not charged:
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed — stock released")
        return False

    # Phase 3: Success. Stock is already deducted via reserve.
    print(f"Order {order_id}: SUCCESS")
    return True
