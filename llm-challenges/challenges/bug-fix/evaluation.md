1. The final stock should never be negative.
2. An `asyncio.Lock` (or similar) should be used inside the `Inventory` class.
3. The simulation logic (delays) should remain to prove the fix works under latency.
4. **Efficiency**: The fix should be targeted and not involve rewriting unrelated parts of the system.
5. **Cost**: The LLM should identify the bug quickly and fix it in a single turn if possible.