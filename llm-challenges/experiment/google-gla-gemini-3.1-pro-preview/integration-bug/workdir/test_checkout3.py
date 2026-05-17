import asyncio
from inventory import Inventory
from payments import PaymentGateway
import checkout

async def main():
    inv = Inventory(5)
    gw = PaymentGateway(0)
    print("Initial stock:", inv.stock)
    await checkout.checkout("test", 1, 10, inv, gw)
    print("Stock after 1 checkout:", inv.stock)
    print("Charges:", gw.charges)

asyncio.run(main())
