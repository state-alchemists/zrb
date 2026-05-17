import asyncio
from inventory import Inventory
from payments import PaymentGateway
from checkout import checkout

async def main():
    inv = Inventory(5)
    gw = PaymentGateway(0)
    
    # Try to cause overselling by calling check_stock, then bypass checkout?
    # No, we must use checkout.
    
    orders = [checkout(f"order_1", 1, 100, inv, gw) for i in range(100)]
    await asyncio.gather(*orders)
    print(f"Stock: {inv.stock}")

asyncio.run(main())
