"""Shared exactness checks. Not a test module — pytest does not collect this."""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from types import MappingProxyType

from pydantic import BaseModel


def walk_for_floats(obj, path: str = "value", found: list[str] | None = None) -> list[str]:
    """Every inexact number reachable from `obj`, as a list of paths.

    Handles pydantic models, dataclasses, mappings and sequences. Empty result
    means every number on this object is exact.
    """
    if found is None:
        found = []

    if isinstance(obj, (float, complex)):
        found.append(f"{path} = {obj!r}")
        return found
    if isinstance(obj, Fraction):
        if not isinstance(obj.numerator, int) or not isinstance(obj.denominator, int):
            found.append(f"{path} is a Fraction over non-integers")
        return found
    if isinstance(obj, (str, bytes, int, bool)) or obj is None:
        return found
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            walk_for_floats(getattr(obj, name), f"{path}.{name}", found)
        return found
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for field in dataclasses.fields(obj):
            walk_for_floats(getattr(obj, field.name), f"{path}.{field.name}", found)
        return found
    if isinstance(obj, (dict, MappingProxyType)):
        for key, value in obj.items():
            walk_for_floats(value, f"{path}[{key!r}]", found)
        return found
    if isinstance(obj, (list, tuple, set, frozenset)):
        for index, value in enumerate(obj):
            walk_for_floats(value, f"{path}[{index}]", found)
        return found
    return found


def assert_exact(obj, label: str = "value") -> None:
    found = walk_for_floats(obj, label)
    assert not found, "inexact numbers found:\n  " + "\n  ".join(found)
