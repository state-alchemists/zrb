import asyncio


class InventoryBuggy:
    def __init__(self):
        self.stock = 10
        # NO LOCK - THIS IS THE BUG!

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # RACE CONDITION: Check and decrement are NOT atomic
        if self.stock >= amount:
            # Simulate DB latency
            await asyncio.sleep(0.1)
            self.stock -= amount
            print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
            return True
        else:
            print(f"User {user_id} failed to purchase. Stock low.")
            return False


async def main():
    inventory = InventoryBuggy()

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    # Should result in negative stock if not handled correctly.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")
    print(f"Expected: >= 0 (min 1 if 3 successful purchases of 3 each)")


if __name__ == "__main__":
    asyncio.run(main())
