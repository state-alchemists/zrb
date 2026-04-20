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
    # Phase 1: atomically reserve stock so inventory can never go below zero
    reserved = await inventory.reserve(quantity)
    if not reserved:
        print(f"Order {order_id}: out of stock")
        return False

    try:
        # Phase 2: attempt to charge the customer; charge is idempotent
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            # Payment failed – release the reservation so stock is available
            await inventory.release(quantity)
            print(f"Order {order_id}: payment failed")
            return False

        # In this simplified model, confirmation is a no-op but kept for clarity
        await inventory.confirm(quantity)

        print(f"Order {order_id}: SUCCESS")
        return True
    except Exception as exc:  # Defensive: in case of unexpected errors
        # Best-effort compensation: release reserved stock
        await inventory.release(quantity)
        print(f"Order {order_id}: error during checkout ({exc})")
        return False
