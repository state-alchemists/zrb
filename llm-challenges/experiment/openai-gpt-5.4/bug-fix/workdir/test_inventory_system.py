import asyncio
import unittest

from inventory_system import Inventory


class InventoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_purchases_do_not_oversell_stock(self):
        inventory = Inventory()

        results = await asyncio.gather(*(inventory.purchase(i, 3) for i in range(5)))

        self.assertEqual(results.count(True), 3)
        self.assertEqual(results.count(False), 2)
        self.assertEqual(inventory.stock, 1)
        self.assertGreaterEqual(inventory.stock, 0)
