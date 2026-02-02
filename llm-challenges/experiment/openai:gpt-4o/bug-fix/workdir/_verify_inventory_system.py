import asyncio

from inventory_system import Inventory


async def main():
    inventory = Inventory()

    # Simulating more users to stress test lock
    tasks = [
        inventory.purchase(i, 3) for i in range(10)
    ]  # Total demand = 30, Stock = 10

    await asyncio.gather(*tasks)

    print(f"Final Stock after stress test: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
