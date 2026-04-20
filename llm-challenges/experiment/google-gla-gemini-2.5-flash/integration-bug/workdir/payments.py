import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_orders: Set[str] = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if order_id in self._charged_orders:
            print(f"Order {order_id}: already charged, preventing duplicate")
            return False
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        self._charged_orders.add(order_id)
        return True

    async def refund(self, order_id: str, amount: float) -> None:
        await asyncio.sleep(0.01)
        self.total_charged -= amount
        # In a real system, you'd mark the original charge as refunded or remove it.
        # For this simulation, we'll just adjust the total and remove from charged_orders.
        self.charges = [c for c in self.charges if c["order_id"] != order_id]
        if order_id in self._charged_orders:
            self._charged_orders.remove(order_id)
