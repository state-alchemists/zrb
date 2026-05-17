import asyncio
from inventory import Inventory
from payments import PaymentGateway

_locks = {}
_locks_lock = asyncio.Lock()

async def _get_lock(order_id: str):
    async with _locks_lock:
        if order_id not in _locks:
            _locks[order_id] = asyncio.Lock()
        return _locks[order_id]

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    lock = await _get_lock(order_id)
    async with lock:
        # Check if already charged to prevent double charging
        if any(c["order_id"] == order_id for c in gateway.charges):
            return True

        decremented = await inventory.decrement(quantity)
        if not decremented:
            print(f"Order {order_id}: out of stock")
            return False

        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            print(f"Order {order_id}: payment failed")
            await inventory.increment(quantity)
            return False

        print(f"Order {order_id}: SUCCESS")
        return True

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0.0)
    
    # Try 3 concurrent checkouts for order_1
    results = await asyncio.gather(
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_1", 1, 100, inventory, gateway),
        checkout("order_2", 1, 100, inventory, gateway),
    )
    
    print("Results:", results)
    print("Stock:", inventory.stock)
    print("Charges:", gateway.charges)

asyncio.run(main())
