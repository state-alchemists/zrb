from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    reserved = await inventory.try_reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    amount = quantity * price
    charged = await gateway.charge_once(order_id, amount)
    if not charged:
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
