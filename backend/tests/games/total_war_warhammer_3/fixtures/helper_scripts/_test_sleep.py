"""Test fixture: prints 'starting', sleeps 30s, prints 'done'."""

import sys
import time

print("starting", flush=True)
time.sleep(30)
print("done", flush=True)
sys.exit(0)
