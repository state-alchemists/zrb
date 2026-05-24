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
    reservation_id = None
    charge_id = None
    try:
        # 1. Reserve stock
        reservation_id = await inventory.reserve_stock(quantity)
        if not reservation_id:
            print(f"Order {order_id}: out of stock or reservation failed")
            return False

        # 2. Attempt to charge
        charge_id = await gateway.charge(order_id, quantity * price)
        if not charge_id:
            print(f"Order {order_id}: payment failed. Cancelling stock reservation.")
            await inventory.cancel_reservation(reservation_id)
            return False

        # 3. Decrement reserved stock. If this fails, refund payment and cancel reservation.
        if not await inventory.decrement_reserved(reservation_id):
            print(f"Order {order_id}: inventory error after payment and reservation — item not delivered. Refunding payment.")
            await gateway.refund(charge_id)
            return False

        # 4. Capture payment. If this fails, refund payment and cancel reservation.
        if not await gateway.capture_payment(charge_id):
            print(f"Order {order_id}: payment capture failed, potentially duplicate or invalid charge. Refunding payment and cancelling stock reservation.")
            await inventory.cancel_reservation(reservation_id)
            await gateway.refund(charge_id)
            return False

        print(f"Order {order_id}: SUCCESS")
        return True
    except Exception as e:
        print(f"Order {order_id}: An unexpected error occurred: {e}")
        # Ensure resources are released in case of unexpected errors
        if charge_id:
            await gateway.refund(charge_id)
        if reservation_id:
            await inventory.cancel_reservation(reservation_id)
        return False
