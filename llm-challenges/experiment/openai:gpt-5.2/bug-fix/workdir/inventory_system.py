import asyncio
from dataclasses import dataclass, field


@dataclass
class Inventory:
    stock: int = 10
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def purchase(self, user_id: int, amount: int) -> bool:
        """Attempt to purchase `amount` items.

        This method is safe under concurrent load: the check and decrement are
        performed atomically while holding a lock.
        """
        if amount <= 0:
            raise ValueError("amount must be positive")

        print(f"User {user_id} checking stock...")

        # Keep the critical section minimal: do NOT await inside the lock.
        async with self._lock:
            if self.stock < amount:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False
            self.stock -= amount
            remaining = self.stock

        # Simulate DB latency outside the lock (e.g., payment / persistence).
        await asyncio.sleep(0.1)
        print(f"User {user_id} purchased {amount}. Remaining: {remaining}")
        return True


async def main() -> None:
    inventory = Inventory(stock=10)

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
