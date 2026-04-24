import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._processed_orders: Set[str] = set()
        self._refunded_orders: Set[str] = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        """Charge an order. Idempotent - same order_id only charged once."""
        await asyncio.sleep(0.03)
        # Idempotency: prevent duplicate charges for same order_id
        if order_id in self._processed_orders:
            return True  # Already processed, return success
        if order_id in self._refunded_orders:
            # This order was refunded, don't allow recharge
            self._refunded_orders.discard(order_id)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        self._processed_orders.add(order_id)
        return True

    async def refund(self, order_id: str, amount: float) -> None:
        """Process a refund for an order."""
        await asyncio.sleep(0.02)
        if order_id in self._refunded_orders:
            return  # Already refunded
        self.total_charged -= amount
        self._refunded_orders.add(order_id)
        # Remove from charges list
        self.charges = [c for c in self.charges if c["order_id"] != order_id]
