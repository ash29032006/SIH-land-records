"""Class 2 fixtures. Three per rule: violates, passes, witness missing.

The "passes" fixture matters most here. Conservation is the flagship claim, and a
conservation rule that fires on records that do add up would discredit it.
"""

from __future__ import annotations

from fractions import Fraction

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.records import TenureTotal
from kavach.rules import conservation
