import asyncio
from account import transfer, db

async def main():
    print("Initial Balances:")
    print(f"Alice: {await db.get_balance('Alice')}")
    print(f"Bob: {await db.get_balance('Bob')}")
    
    # Simulate 5 simultaneous transfers of $20 from Alice to Bob
    # Alice starts with $100. Bob starts with $100.
    # Total money should remain $200.
    tasks = [transfer("Alice", "Bob", 20) for _ in range(5)]
    await asyncio.gather(*tasks)
    
    print("\nFinal Balances:")
    alice_final = await db.get_balance('Alice')
    bob_final = await db.get_balance('Bob')
    print(f"Alice: {alice_final}")
    print(f"Bob: {bob_final}")
    print(f"Total: {alice_final + bob_final}")

if __name__ == "__main__":
    asyncio.run(main())
