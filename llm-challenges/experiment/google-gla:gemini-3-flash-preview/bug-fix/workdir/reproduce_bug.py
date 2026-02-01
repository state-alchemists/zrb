import asyncio

class Inventory:
    def __init__(self):
        self.stock = 10

    async def purchase(self, user_id, amount):
        if self.stock >= amount:
            await asyncio.sleep(0.1) # Context switch
            self.stock -= amount
            return True
        return False

async def main():
    inventory = Inventory()
    tasks = [inventory.purchase(i, 3) for i in range(5)]
    await asyncio.gather(*tasks)
    print(f"Final Stock: {inventory.stock}")

if __name__ == "__main__":
    asyncio.run(main())
