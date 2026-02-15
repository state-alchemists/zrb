import asyncio
import threading
from typing import Dict, Tuple

class Database:
    """A very slow and unreliable database simulator."""
    def __init__(self):
        self.data = {
            "Alice": 100,
            "Bob": 100
        }
        self._lock = threading.Lock()

    async def get_balance(self, user):
        await asyncio.sleep(0.05)
        return self.data.get(user, 0)

    async def set_balance(self, user, amount):
        await asyncio.sleep(0.05)
        self.data[user] = amount
    
    async def atomic_transfer(self, from_user: str, to_user: str, amount: float) -> bool:
        """
        Atomically transfer money between users.
        Returns True if successful, False if insufficient funds.
        """
        # Use threading lock for synchronization across async tasks
        with self._lock:
            # Check balance
            from_balance = self.data.get(from_user, 0)
            if from_balance < amount:
                return False
            
            # Perform transfer
            self.data[from_user] = from_balance - amount
            self.data[to_user] = self.data.get(to_user, 0) + amount
            
            # Simulate database delay (outside lock to allow concurrency)
            # But we need to keep atomicity, so delay after critical section
            pass
        
        # Simulate database delay after releasing lock
        await asyncio.sleep(0.05)
        return True
