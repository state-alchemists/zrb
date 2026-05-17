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
    available = await inventory.check_stock(quantity)
    if not available:
        print(f"Order {order_id}: out of stock")
        return False

    # To avoid ghost charges, we must ensure that we never charge a
    # customer unless we can also guarantee delivery of the item.
    # We achieve this by performing the atomic stock decrement *before*
    # charging the payment gateway. If the decrement fails, no charge is
    # attempted.
    decremented = await inventory.decrement(quantity)
    if not decremented:
        print(
            f"Order {order_id}: inventory changed concurrently; could not reserve stock"
        )
        return False

    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        # Payment failed after reserving stock. To keep inventory and
        # charges consistent, we release the reserved stock.
        await inventory.increment(quantity)
        print(f"Order {order_id}: payment failed, stock released")
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
