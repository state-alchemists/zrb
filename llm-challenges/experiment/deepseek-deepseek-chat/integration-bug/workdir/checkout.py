from inventory import Inventory
from payments import PaymentGateway


async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    # Reserve inventory first — atomic gate prevents overselling.
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    # Now attempt payment.
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed — release the reservation.
        await inventory.release(quantity)
        print(f"Order {order_id}: payment failed, reservation released")
        return False

    # Both reserve and charge succeeded — order is confirmed.
    print(f"Order {order_id}: SUCCESS")
    return True
