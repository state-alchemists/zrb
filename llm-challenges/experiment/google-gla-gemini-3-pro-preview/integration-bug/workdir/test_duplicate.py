import asyncio
from inventory import Inventory
from payments import PaymentGateway

_processing_orders = set()
_completed_orders = set()

async def checkout(
    order_id: str,
    quantity: int,
    price: float,
    inventory: Inventory,
    gateway: PaymentGateway,
) -> bool:
    if order_id in _completed_orders or order_id in _processing_orders:
        return False
    _processing_orders.add(order_id)
    
    try:
        decremented = await inventory.decrement(quantity)
        if not decremented:
            return False
            
        charged = await gateway.charge(order_id, quantity * price)
        if not charged:
            await inventory.increment(quantity)
            return False
            
        _completed_orders.add(order_id)
        return True
    finally:
        _processing_orders.remove(order_id)

async def main():
    inventory = Inventory(5)
    gateway = PaymentGateway(failure_rate=0)
    
    results = await asyncio.gather(
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_1", 1, 100.0, inventory, gateway)
    )
    print("Results:", results)
    print("Charges:", gateway.charges)

if __name__ == "__main__":
    asyncio.run(main())
