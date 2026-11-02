"""Test fixture: imports a sibling module the same way real registry files do."""

from sibling_constants import SAMPLE_VALUE

WITH_SIBLING = [{"name": "uses sibling", "value": SAMPLE_VALUE}]
