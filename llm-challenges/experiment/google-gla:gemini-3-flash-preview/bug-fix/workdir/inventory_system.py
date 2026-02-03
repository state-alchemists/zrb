import asyncio
import random
import threading


class Inventory:
    def __init__(self):
        self.stock = 10
        self._lock = threading.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Use threading.Lock to ensure thread-safety across multiple threads/loops.
        # We perform the check and decrement in one atomic step to maintain data integrity.
        success = False
        remaining_after_purchase = 0
        with self._lock:
            if self.stock >= amount:
                self.stock -= amount
                remaining_after_purchase = self.stock
                success = True

        if success:
            # Simulate DB latency outside the lock to allow higher concurrency and better performance under load.
            # Holding the lock during I/O (like sleep or DB calls) is a common cause of performance bottlenecks.
            await asyncio.sleep(0.1)
            print(
                f"User {user_id} purchased {amount}. Remaining: {remaining_after_purchase}"
            )
            return True
        else:
            print(f"User {user_id} failed to purchase. Stock low.")
            return False


async def main():
    inventory = Inventory()

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    # The system should allow 3 successes and 2 failures, leaving 1 item in stock.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
