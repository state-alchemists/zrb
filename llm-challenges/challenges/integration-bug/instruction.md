# E-Commerce Checkout Service

Users have reported two production incidents:

1. **Overselling**: Items are sometimes sold even when out of stock. Inventory goes negative.
2. **Ghost charges**: Customers are occasionally charged but receive no item, with no record of a successful order.

The checkout flow is in `checkout.py`. It uses `inventory.py` (stock management) and `payments.py` (mock payment gateway).

`main.py` runs a concurrent simulation — run it to reproduce the issues.

Fix the checkout logic. The fix must ensure:
- Inventory never goes below zero
- Every successful charge corresponds to exactly one item delivered
- No order is charged more than once

Do not change the public interfaces of `Inventory` or `PaymentGateway`. You may add methods to them.
