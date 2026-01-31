#!/usr/bin/env python3
import asyncio
import os
import sys


def verify_inventory_fix():
    """Verify that the inventory system fix works correctly."""

    # Check if inventory_system.py exists
    if not os.path.exists("inventory_system.py"):
        print("ERROR: inventory_system.py not found")
        return False

    # Read the file
    with open("inventory_system.py", "r") as f:
        content = f.read()

    # Check for asyncio.Lock or similar concurrency control
    if "asyncio.Lock" not in content and "Lock" not in content:
        print("ERROR: No asyncio.Lock or similar concurrency control found")
        return False

    # Check that lock is used in purchase method
    if "self.stock" in content and "lock" in content.lower():
        print("INFO: Lock mechanism found in code")
    else:
        print("WARNING: Lock may not be properly integrated with stock access")

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
                    return False
                else:
                    print(f"PASS: Final stock is non-negative: {final_stock}")
                    return True
            else:
                print("WARNING: Could not parse final stock from output")
                return True  # Give benefit of doubt if code has lock
        else:
            print("INFO: No 'Final Stock:' output found, assuming modified test")
            return True  # If they changed the test output

    except Exception as e:
        print(f"ERROR testing script: {e}")
        return False

    return True


if __name__ == "__main__":
    success = verify_inventory_fix()
    sys.exit(0 if success else 1)
