import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._lock = asyncio.Lock()
        self._in_progress: Set[str] = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        async with self._lock:
            for c in self.charges:
                if c["order_id"] == order_id:
                    return True
            while order_id in self._in_progress:
                await asyncio.sleep(0.01)
            for c in self.charges:
                if c["order_id"] == order_id:
                    return True
            self._in_progress.add(order_id)

        try:
            await asyncio.sleep(0.03)
            if random.random() < self._failure_rate:
                return False
            
            async with self._lock:
                for c in self.charges:
                    if c["order_id"] == order_id:
                        return True
                self.total_charged += amount
                self.charges.append({"order_id": order_id, "amount": amount})
                return True
        finally:
            async with self._lock:
                self._in_progress.discard(order_id)
