# Race Condition Fix - Inventory System

## Problem
Users reported that inventory count was sometimes incorrect when multiple purchases happened simultaneously.

## Root Cause
Without proper synchronization, concurrent `purchase()` calls could cause a race condition:
1. User A checks stock: 10 >= 3 ✓
2. User B checks stock: 10 >= 3 ✓
3. User A decrements: 10 - 3 = 7
4. User B decrements: 7 - 3 = 4
5. Stock becomes negative when demand exceeds supply

## Solution Implemented
The fix uses `asyncio.Lock()` to ensure atomic check-and-decrement operations:

```python
class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        async with self.lock:
            if self.stock >= amount:
                await asyncio.sleep(0.1)  # Simulate DB latency
                self.stock -= amount
                return True
            return False
```

## Key Points
1. **Lock Acquisition**: `async with self.lock:` acquires the lock before any operation
2. **Atomicity**: Both the stock check (`if self.stock >= amount`) and the decrement (`self.stock -= amount`) happen atomically within the lock
3. **Isolation**: Each purchase operation runs in isolation, preventing interleaving

## Verification Results

### Test 1: Basic Concurrency (5 users, 3 items each)
- Initial stock: 10
- Total demand: 15
- Successful purchases: 3 (9 items sold)
- Final stock: 1
- **✓ Stock never negative**

### Test 2: Heavy Load (20 users, 1 item each)
- Initial stock: 10
- Total demand: 20
- Successful purchases: 10 (10 items sold)
- Final stock: 0
- **✓ All integrity checks passed**

### Test 3: Race Condition Demonstration
- **Without lock**: Stock goes to -5 (race condition!)
- **With lock**: Stock stays at 1 (data integrity maintained)

## Conclusion
The `asyncio.Lock()` mechanism successfully prevents race conditions in the inventory system by ensuring that stock check and decrement operations are atomic. Data integrity is maintained under concurrent load.