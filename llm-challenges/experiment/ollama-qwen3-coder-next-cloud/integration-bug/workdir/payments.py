import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_orders: Set[str] = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True

    async def charge_once(self, order_id: str, amount: float) -> bool:
        """Charge only if order_id hasn't been charged before. Returns True if charge succeeded."""
        async with self._lock:
            if order_id in self._charged_orders:
                return True  # Already charged, skip
            await asyncio.sleep(0.03)
            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            self._charged_orders.add(order_id)
            return True

    async def is_charged(self, order_id: str) -> bool:
        async with self._lock:
            return order_id in self._charged_orders

    async def rollback_charge(self, order_id: str) -> Optional[float]:
        """Remove a charge for an order that failed after payment. Returns amount if found."""
        async with self._lock:
            if order_id in self._charged_orders:
                self._charged_orders.discard(order_id)
                for i, c in enumerate(self.charges):
                    if c["order_id"] == order_id:
                        amount = c["amount"]
                        self.charges.pop(i)
                        self.total_charged -= amount
                        return amount
            return None
