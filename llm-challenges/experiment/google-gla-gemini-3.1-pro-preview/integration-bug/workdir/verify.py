#!/usr/bin/env python3
import asyncio
import os
import sys
import importlib.util

def verify():
    print("Verifying Integration Bug Fix...")
    
    if not os.path.exists("bank.py") or not os.path.exists("account.py"):
        print("FAIL: Missing core files")
        return False

    try:
        # Import the module and run main
        spec = importlib.util.spec_from_file_location("bank", "bank.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # We need to capture the db state after running main
        asyncio.run(module.main())
        
        db = module.db
        alice_final = asyncio.run(db.get_balance('Alice'))
        bob_final = asyncio.run(db.get_balance('Bob'))
        total = alice_final + bob_final
        
        print(f"Total Money in System: {total}")
        
        if total != 200:
            print(f"FAIL: Money was lost or created! Total: {total}")
            print("VERIFICATION_RESULT: FAIL")
            return False
            
        if alice_final < 0 or bob_final < 0:
            print("FAIL: Negative balance detected")
            print("VERIFICATION_RESULT: FAIL")
            return False

        # Check for some form of locking or atomicity
        with open("account.py", "r") as f:
            content = f.read()
            if "Lock" not in content and "transaction" not in content.lower():
                print("WARNING: No explicit locking found, might be lucky or uses different pattern")
        
        print("PASS: System integrity maintained")
        print("VERIFICATION_RESULT: EXCELLENT")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        print("VERIFICATION_RESULT: FAIL")
        return False

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
