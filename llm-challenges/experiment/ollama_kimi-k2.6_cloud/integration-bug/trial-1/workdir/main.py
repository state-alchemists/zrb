import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

ITEM_PRICE = 100.0
INITIAL_STOCK = 5
NUM_ORDERS = 12


async def main() -> None:
    inventory = Inventory(INITIAL_STOCK)
    gateway = PaymentGateway(failure_rate=0.25)

    print(f"Starting simulation: {NUM_ORDERS} concurrent orders, stock={INITIAL_STOCK}")
    orders = [
        checkout(f"order_{i}", 1, ITEM_PRICE, inventory, gateway)
        for i in range(NUM_ORDERS)
    ]
    results = await asyncio.gather(*orders)

    successful = sum(results)
    items_sold = INITIAL_STOCK - inventory.stock
    charge_ids = [c["order_id"] for c in gateway.charges]
    duplicates = len(charge_ids) - len(set(charge_ids))

    print(f"\n=== Results ===")
    print(f"Successful orders:  {successful}")
    print(f"Items sold:         {items_sold}  (initial stock: {INITIAL_STOCK})")
    print(f"Remaining stock:    {inventory.stock}")
    print(f"Total charged:      ${gateway.total_charged:.2f}")
    print(f"Expected charge:    ${successful * ITEM_PRICE:.2f}")
    print(f"Duplicate charges:  {duplicates}")

    if inventory.stock < 0:
        print("ERROR: Inventory went negative!")
    if abs(gateway.total_charged - successful * ITEM_PRICE) > 0.01:
        print("ERROR: Charge amount does not match successful orders!")
    if duplicates > 0:
        print("ERROR: Duplicate charges detected!")


if __name__ == "__main__":
    asyncio.run(main())
