"""Class 1 fixtures. Three per rule: violates, passes, witness missing.

AGENTS.md 4.2. The "passes" fixture is the false-positive guard and matters most:
a rule that fires on a correct record costs a family money.
"""

from __future__ import annotations

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.rules import grammar
