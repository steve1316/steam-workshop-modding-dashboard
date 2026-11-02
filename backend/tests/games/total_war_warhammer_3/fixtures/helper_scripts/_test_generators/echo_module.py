"""Test fixture: a module run with `python -m` from the helper_scripts root, importing a sibling package like the real generators do."""

import sys

from _test_core.values import GREETING

print(GREETING, flush=True)
sys.exit(0)
