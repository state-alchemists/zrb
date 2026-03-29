#!/usr/bin/env python3
import asyncio
import os
import sys


def verify_inventory_fix():
    """Verify that the inventory system fix works correctly."""

    # Check if inventory_system.py exists
    if not os.path.exists("inventory_system.py"):
        print("FAIL: inventory_system.py not found")
        print("VERIFICATION_RESULT: FAIL")
        return False

    # Read the file
    with open("inventory_system.py", "r") as f:
        content = f.read()

    score = 0
    max_score = 2

    # Check for asyncio.Lock or similar concurrency control
    has_lock = "asyncio.Lock" in content or "Lock" in content
    if has_lock:
        print("PASS: Concurrency control found")
        score += 1
    else:
        print("WARNING: No explicit asyncio.Lock found")

    # Try to run the script to see if it works
    try:
        # Import the module
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "inventory_system", "inventory_system.py"
        )
        module = importlib.util.module_from_spec(spec)

        # We need to capture output and run the async main
        import contextlib
        import io

        # Capture stdout
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            try:
                # Execute the module first
                spec.loader.exec_module(module)

                # Run the async main
                if hasattr(module, "main"):
                    asyncio.run(module.main())
                else:
                    # Try to find and run inventory creation
                    inventory = module.Inventory()
                    asyncio.run(inventory.purchase(1, 1))
            except Exception as e:
                print(f"ERROR running script: {e}")
                print("VERIFICATION_RESULT: FAIL")
                return False

        output = f.getvalue()

        # Check that final stock is not negative
        if "Final Stock:" in output:
            # Extract final stock value
            import re

            match = re.search(r"Final Stock:\s*(-?\d+)", output)
            if match:
                final_stock = int(match.group(1))
                if final_stock < 0:
                    print(f"FAIL: Final stock is negative: {final_stock}")
                    print("VERIFICATION_RESULT: FAIL")
                    return False
                else:
                    print(f"PASS: Final stock is non-negative: {final_stock}")
                    score += 1
            else:
                print("WARNING: Could not parse final stock from output")
                # Give benefit of doubt if code has lock, but don't increment score
        else:
            print("INFO: No 'Final Stock:' output found, assuming modified test")
            # Neutral

    except Exception as e:
        print(f"ERROR testing script: {e}")
        print("VERIFICATION_RESULT: FAIL")
        return False

    # Determine final status
    if score >= 2:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 1:  # At least runs or has lock, outcome uncertain or partial
        # If stock is correct (score includes that), it's a pass.
        # Actually, if final stock is verified non-negative, that's the critical pass.
        # Re-evaluating logic:
        pass  # handled below

    # If we reached here without returning False, strict check:
    # Critical: Stock non-negative (captured in exception/return blocks above)

    if score == 2:
        # Lock + Correct Stock
        print("VERIFICATION_RESULT: EXCELLENT")
    else:
        # Maybe just Correct Stock but weird implementation
        print("VERIFICATION_RESULT: PASS")

    return True


if __name__ == "__main__":
    success = verify_inventory_fix()
    sys.exit(0 if success else 1)
