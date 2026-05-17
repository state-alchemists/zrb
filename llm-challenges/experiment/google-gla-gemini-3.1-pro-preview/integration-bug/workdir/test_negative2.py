import asyncio
from inventory import Inventory
from checkout import checkout
from payments import PaymentGateway

async def test():
    inv = Inventory(1)
    gateway = PaymentGateway(0)
    await asyncio.gather(*[checkout(f"order_{i}", 1, 100, inv, gateway) for i in range(10)])
    print("Stock:", inv.stock)

asyncio.run(test())
