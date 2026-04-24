import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self._total_charged: float = 0.0
        self._charges: List[dict] = []
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        async with self._lock:
            await asyncio.sleep(0.03)
            for charge in self._charges:
                if charge["order_id"] == order_id and charge["status"] == "success":
                    return True  # Idempotent: already charged successfully

            if random.random() < self._failure_rate:
                self._charges.append({"order_id": order_id, "amount": amount, "status": "failed"})
                return False
            
            self._total_charged += amount
            self._charges.append({"order_id": order_id, "amount": amount, "status": "success"})
            return True

    async def refund(self, order_id: str, amount: float) -> bool:
        async with self._lock:
            for charge in self._charges:
                if charge["order_id"] == order_id and charge["status"] == "success":
                    self._total_charged -= amount
                    charge["status"] = "refunded"
                    return True
            return False

    @property
    def total_charged(self) -> float:
        return self._total_charged

    @property
    def charges(self) -> List[dict]:
        return self._charges