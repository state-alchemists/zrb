import asyncio
import importlib
import unittest

import account


class TransferTests(unittest.TestCase):
    def setUp(self):
        global account
        account = importlib.reload(account)

    def test_concurrent_transfers_are_atomic(self):
        async def scenario():
            results = await asyncio.gather(
                *(account.transfer("Alice", "Bob", 20) for _ in range(5))
            )
            alice = await account.db.get_balance("Alice")
            bob = await account.db.get_balance("Bob")
            return results, alice, bob

        results, alice, bob = asyncio.run(scenario())

        self.assertEqual([True, True, True, True, True], results)
        self.assertEqual(0, alice)
        self.assertEqual(200, bob)
        self.assertEqual(200, alice + bob)

    def test_transfer_rejects_insufficient_funds(self):
        async def scenario():
            result = await account.transfer("Alice", "Bob", 200)
            alice = await account.db.get_balance("Alice")
            bob = await account.db.get_balance("Bob")
            return result, alice, bob

        result, alice, bob = asyncio.run(scenario())

        self.assertFalse(result)
        self.assertEqual(100, alice)
        self.assertEqual(100, bob)
        self.assertEqual(200, alice + bob)


if __name__ == "__main__":
    unittest.main()
