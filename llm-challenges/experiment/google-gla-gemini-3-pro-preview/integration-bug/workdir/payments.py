import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._processed = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        if order_id in self._processed:
            return False
        self._processed.add(order_id)
        
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            self._processed.remove(order_id)
            return False
            
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True
