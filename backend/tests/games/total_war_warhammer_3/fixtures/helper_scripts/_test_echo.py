"""Test fixture: prints 5 lines and exits 0."""

import sys

for i in range(5):
    print(f"line {i}", flush=True)
sys.exit(0)
