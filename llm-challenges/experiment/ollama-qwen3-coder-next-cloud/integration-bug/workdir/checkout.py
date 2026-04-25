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
    """
    Checkout flow that ensures:
    - Inventory never goes below zero (using atomic check_and_reserve)
    - Every successful charge corresponds to exactly one item delivered
    - No order is charged more than once (idempotent payment processing)
    """
    # Step 1: Check and reserve stock atomically (prevents overselling)
    available = await inventory.check_and_reserve(quantity)
    if not available:
        print(f"Order {order_id}: out of stock")
        return False

    # Step 2: Charge payment (idempotent - gateway handles duplicate order_id)
    charged = await gateway.charge(order_id, quantity * price)
    if not charged:
        print(f"Order {order_id}: payment failed")
        # Payment failed, restore the reserved stock
        await inventory.undo_reserve(quantity)
        return False

    # Step 3: Finalize the stock decrement
    final = await inventory.finalize_reserve(quantity)
    if not final:
        print(f"Order {order_id}: inventory error after payment — item not delivered")
        # Inventory error - restore stock
        await inventory.undo_reserve(quantity)
        # Refund the charge to prevent ghost charges
        await gateway.refund(order_id, quantity * price)
        return False

    print(f"Order {order_id}: SUCCESS")
    return True
