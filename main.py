import os

NAME = os.getenv("NAME", "world")

if __name__ == "__main__":
    print(f"Hello {NAME}")
