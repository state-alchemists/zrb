import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True

    async def refund(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(00.03)
        # In a real system, this would interact with the payment gateway to issue a refund.
        # For this simulation, we'll just adjust the total_charged and remove the charge.
        for i, charge in enumerate(self.charges):
            if charge["order_id"] == order_id and charge["amount"] == amount:
                self.total_charged -= amount
                self.charges.pop(i)
                return True
        return False
