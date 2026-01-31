import asyncio
import random


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()
        self.failures = 0

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Acquire lock to ensure atomic check-and-decrement operation
        async with self.lock:
            if self.stock >= amount:
                # Simulate DB latency
                await asyncio.sleep(0.1)

                # Simulate random failure after stock check but before decrement
                if random.random() < 0.3:  # 30% chance of failure
                    self.failures += 1
                    print(f"User {user_id} - SIMULATED FAILURE after stock check!")
                    raise Exception("Database connection failed")

                self.stock -= amount
                print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
                return True
            else:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False


async def main():
    inventory = Inventory()

    # 5 users trying to buy 3 items each
    tasks = []
    for i in range(5):
        task = inventory.purchase(i, 3)

        # Wrap task to handle exceptions
        async def safe_purchase(user_id, task):
            try:
                return await task
            except Exception as e:
                print(f"User {user_id} encountered error: {e}")
                return False

        tasks.append(safe_purchase(i, task))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    print(f"\nFinal Stock: {inventory.stock}")
    print(f"Successful purchases: {sum(1 for r in results if r is True)}")
    print(f"Failures simulated: {inventory.failures}")

    # Check if stock is correct
    expected_successful = sum(1 for r in results if r is True)
    expected_stock = 10 - (expected_successful * 3)

    if inventory.stock != expected_stock:
        print(
            f"ERROR: Stock mismatch! Expected: {expected_stock}, Actual: {inventory.stock}"
        )
    else:
        print(f"Stock correct: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
