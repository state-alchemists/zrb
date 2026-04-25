#!/usr/bin/env python3
import asyncio
import os
import random
import sys


def verify():
    print("Verifying Checkout Fix...")

    for fname in ["inventory.py", "payments.py", "checkout.py"]:
        if not os.path.exists(fname):
            print(f"FAIL: {fname} not found")
            print("VERIFICATION_RESULT: FAIL")
            return False

    sys.path.insert(0, os.getcwd())
    try:
        from inventory import Inventory
        from payments import PaymentGateway
        from checkout import checkout
    except ImportError as e:
        print(f"FAIL: Import error: {e}")
        print("VERIFICATION_RESULT: FAIL")
        return False

    with open("inventory.py") as f:
        inv_src = f.read()
    with open("checkout.py") as f:
        checkout_src = f.read()
    has_lock = "Lock" in inv_src or "Lock" in checkout_src

    async def run_trial(seed: int):
        random.seed(seed)
        inventory = Inventory(5)
        gateway = PaymentGateway(failure_rate=0.25)
        orders = [checkout(f"order_{i}", 1, 100.0, inventory, gateway) for i in range(12)]
        results = await asyncio.gather(*orders)
        successful = sum(results)
        charge_ids = [c["order_id"] for c in gateway.charges]
        duplicates = len(charge_ids) - len(set(charge_ids))
        expected_charge = successful * 100.0
        return inventory.stock, gateway.total_charged, successful, duplicates, expected_charge

    async def run_all_trials():
        results = []
        for trial in range(6):
            random.seed(trial * 7)
            inventory = Inventory(5)
            gateway = PaymentGateway(failure_rate=0.25)
            orders = [checkout(f"order_{i}", 1, 100.0, inventory, gateway) for i in range(12)]
            trial_results = await asyncio.gather(*orders)
            successful = sum(trial_results)
            charge_ids = [c["order_id"] for c in gateway.charges]
            duplicates = len(charge_ids) - len(set(charge_ids))
            expected_charge = successful * 100.0
            results.append((inventory.stock, gateway.total_charged, successful, duplicates, expected_charge))
        return results

    all_results = asyncio.run(run_all_trials())

    passes = 0
    trials = len(all_results)
    for trial, (stock, charged, successful, dupes, expected) in enumerate(all_results):
        errors = []
        if stock < 0:
            errors.append(f"negative stock ({stock})")
        if abs(charged - expected) > 0.01:
            errors.append(f"charge mismatch (charged={charged:.2f}, expected={expected:.2f})")
        if dupes > 0:
            errors.append(f"{dupes} duplicate charge(s)")

        if errors:
            print(f"  Trial {trial + 1}: FAIL — {', '.join(errors)}")
        else:
            print(f"  Trial {trial + 1}: PASS (stock={stock}, successful={successful}, charged=${charged:.2f})")
            passes += 1

    if passes < trials:
        print(f"FAIL: Only {passes}/{trials} trials passed")
        print("VERIFICATION_RESULT: FAIL")
        return False

    if has_lock:
        print("PASS: Locking mechanism detected")
        print("VERIFICATION_RESULT: EXCELLENT")
    else:
        print("PASS: All trials passed")
        print("VERIFICATION_RESULT: PASS")
    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
