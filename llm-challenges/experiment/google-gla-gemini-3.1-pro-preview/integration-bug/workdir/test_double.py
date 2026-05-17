import asyncio
from inventory import Inventory
from payments import PaymentGateway
import checkout as ch

async def main():
    inv = Inventory(1)
    gw = PaymentGateway(0)
    
    # Try 3 concurrent checkouts for order_1
    await asyncio.gather(
        ch.checkout("order_1", 1, 100, inv, gw),
        ch.checkout("order_1", 1, 100, inv, gw)
    )
    print("Stock:", inv.stock)
    print("Charges:", gw.charges)

asyncio.run(main())
