import random
import threading
import time


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = threading.Lock()  # Use threading lock instead of asyncio

    def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Acquire lock to ensure atomic check-and-decrement operation
        with self.lock:
            if self.stock >= amount:
                # Simulate DB latency
                time.sleep(0.1)
                self.stock -= amount
                print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
                return True
            else:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False


def test_threading():
    """Test with actual threads instead of asyncio"""
    inventory = Inventory()

    def purchase_task(user_id, amount):
        return inventory.purchase(user_id, amount)

    # Create threads
    threads = []
    results = [None] * 5

    for i in range(5):
        thread = threading.Thread(
            target=lambda idx=i: results.__setitem__(idx, purchase_task(idx, 3))
        )
        threads.append(thread)

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print(f"\nFinal Stock: {inventory.stock}")
    print(f"Successful purchases: {sum(1 for r in results if r)}")

    if inventory.stock < 0:
        print(f"ERROR: Negative stock: {inventory.stock}")
        return False

    return True


if __name__ == "__main__":
    print("Testing with threading (multiple OS threads):")
    success = test_threading()

    if success:
        print("\n✓ Threading test passed!")
    else:
        print("\n✗ Threading test failed!")
