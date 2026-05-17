import asyncio
from inventory import Inventory
from payments import PaymentGateway


class CheckoutManager:
    def __init__(self):
        self.processing_orders = set()
        self._lock = asyncio.Lock()

    async def checkout(
        self,
        order_id: str,
        quantity: int,
        price: float,
        inventory: Inventory,
        gateway: PaymentGateway,
    ) -> bool:
        async with self._lock:
            if order_id in self.processing_orders:
                print(f"Order {order_id}: already processing or completed")
                return False
            self.processing_orders.add(order_id)

        try:
            available = await inventory.check_stock(quantity)
            if not available:
                print(f"Order {order_id}: out of stock")
                return False

            charged = await gateway.charge(order_id, quantity * price)
            if not charged:
                print(f"Order {order_id}: payment failed")
                return False

            decremented = await inventory.try_decrement(quantity)
            if not decremented:
                print(f"Order {order_id}: inventory error after payment — item not delivered. Initiating refund.")
                await gateway.refund(order_id, quantity * price)
                return False

            print(f"Order {order_id}: SUCCESS")
            return True
        finally:
            async with self._lock:
                self.processing_orders.remove(order_id)


