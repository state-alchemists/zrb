import asyncio
import threading


class Inventory:
    def __init__(self):
        self.stock = 10
        # Use threading.Lock for true thread-safety across different contexts
        # threading.Lock works with both threads and asyncio (sync context)
        self.lock = threading.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Acquire lock to ensure atomic check-and-decrement operation
        with self.lock:
            if self.stock >= amount:
                # Decrement immediately while holding lock (atomic operation)
                self.stock -= amount
                remaining = self.stock
                success = True
            else:
                remaining = self.stock
                success = False

        # Simulate DB latency outside the lock to avoid blocking other threads
        await asyncio.sleep(0.1)

        if success:
            print(f"User {user_id} purchased {amount}. Remaining: {remaining}")
        else:
            print(f"User {user_id} failed to purchase. Stock low.")

        return success


async def main():
    inventory = Inventory()

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    # Should result in 3 purchases (9 items) and 1 remaining stock.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
