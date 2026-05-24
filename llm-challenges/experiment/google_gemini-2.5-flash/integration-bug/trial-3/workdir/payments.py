import asyncio
import random
import uuid
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._captured_charges: set[str] = set()  # Track successfully captured charges

    async def charge(self, order_id: str, amount: float) -> str | None:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return None
        charge_id = str(uuid.uuid4())
        # Simulate a pending charge. It's not fully captured until capture_payment is called.
        self.charges.append({"order_id": order_id, "amount": amount, "charge_id": charge_id, "status": "pending"})
        return charge_id

    async def capture_payment(self, charge_id: str) -> bool:
        await asyncio.sleep(0.01)
        if charge_id in self._captured_charges:
            return False  # Already captured or invalid charge_id
        for charge in self.charges:
            if charge["charge_id"] == charge_id and charge["status"] == "pending":
                charge["status"] = "captured"
                self.total_charged += charge["amount"]
                self._captured_charges.add(charge_id)
                return True
        return False

    async def refund(self, charge_id: str) -> None:
        await asyncio.sleep(0.01)
        for charge in self.charges:
            if charge["charge_id"] == charge_id and charge["status"] == "pending":
                charge["status"] = "refunded"
                # Note: self.total_charged is only incremented on capture, so no decrement needed here
                break