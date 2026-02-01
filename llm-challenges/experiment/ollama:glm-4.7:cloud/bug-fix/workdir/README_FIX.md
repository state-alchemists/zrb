# Inventory System Race Condition Fix

## Problem

The inventory system had a race condition where the inventory count could become incorrect (negative) when multiple purchases happened simultaneously.

### Root Cause

Without proper locking, the check-and-decrement operation was not atomic:

```python
# BUGGY CODE (without lock)
if self.stock >= amount:        # Multiple threads can pass this check
    await asyncio.sleep(0.1)    # Context switch happens here
    self.stock -= amount        # Multiple threads decrement the same stock
    return True
```

When 5 users try to purchase 3 items each (total demand: 15, stock: 10):
1. All 5 users check stock at the same time - stock is 10, so all pass
2. They all proceed to decrement
3. Stock becomes: 10 → 7 → 4 → 1 → -2 → -5
4. **Result: Negative stock!** ❌

## Solution

Use `asyncio.Lock()` to make the check-and-decrement operation atomic:

```python
# FIXED CODE (with lock)
async with self.lock:  # Ensure only one coroutine executes at a time
    if self.stock >= amount:
        await asyncio.sleep(0.1)
        self.stock -= amount
        return True
```

The lock ensures that only one purchase operation can execute the critical section (check + decrement) at a time.

## Verification Results

### Without Lock (Buggy)
```
Runs: 50
Average final stock: -5.00
Negative stock occurrences: 50
❌ FAIL: Data integrity compromised!
```

### With Lock (Fixed)
```
Runs: 50
Average final stock: 1.00
Negative stock occurrences: 0
✅ PASS: Data integrity maintained!
```

## Usage

```bash
# Run the fixed inventory system
python inventory_system.py

# Run comprehensive stress tests
python test_inventory.py

# Run bug verification (compares buggy vs fixed)
python verify_fix.py
```

## Key Takeaways

1. **Race conditions occur** when shared state is accessed/modified without synchronization
2. **Critical sections** (multiple operations that must be atomic) need protection
3. **asyncio.Lock()** is the correct primitive for async/await code in Python
4. Always test concurrent code under load to uncover race conditions