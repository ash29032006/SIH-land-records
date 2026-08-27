"""Class 3 fixtures. Three per rule: violates, passes, witness missing."""

from __future__ import annotations

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.rules import completeness
