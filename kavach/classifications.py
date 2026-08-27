"""Land classification schemes, loaded as data.

Same reasoning as `units.py`: the taxonomy is regional, and for Bihar it is not
settled (EVIDENCE.md E9). Encoding it as data means a wrong class costs a JSON edit
rather than a code change, and every class states how well sourced it is.

Only one thing in the engine may branch on a class code: whether it is `government`,
which is what Class 2's `raiyati_total + gairmazrua_total == mouza_total` needs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "ClassificationError",
    "ClassificationScheme",
    "DEFAULT_CLASSIFICATIONS_PATH",
    "SchemeRegistry",
    "TenureClass",
    "UnknownScheme",
    "UnknownTenureClass",
    "default_schemes",
    "load_schemes",
]

DEFAULT_CLASSIFICATIONS_PATH = Path(__file__).with_name("classifications.json")

SOURCED = "sourced"
DISPUTED = "disputed"
UNSOURCED = "unsourced"
CONFIDENCE_LEVELS = frozenset({SOURCED, DISPUTED, UNSOURCED})


class ClassificationError(Exception):
    """Base for classification failures."""


class UnknownScheme(ClassificationError):
    pass


class UnknownTenureClass(ClassificationError):
    pass


@dataclass(frozen=True)
class TenureClass:
    code: str
    label: str
    government: bool
    transferable: bool
    confidence: str
    source: str

    @property
    def is_citable(self) -> bool:
        """Whether this class may be quoted outside the codebase."""
        return self.confidence == SOURCED


@dataclass(frozen=True)
class ClassificationScheme:
    id: str
    region: str
    tenure: Mapping[str, TenureClass]
    land_use: tuple[str, ...]
    axis_notes: str
    land_use_note: str

    def tenure_class(self, code: str) -> TenureClass:
        try:
            return self.tenure[code]
        except KeyError:
            raise UnknownTenureClass(
                f"{code!r} is not in scheme {self.id!r} "
                f"(known: {', '.join(sorted(self.tenure))})"
            ) from None

    def is_government(self, code: str) -> bool:
        return self.tenure_class(code).government

    @property
    def tenure_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self.tenure))

    @property
    def disputed_codes(self) -> tuple[str, ...]:
        return tuple(
            sorted(c.code for c in self.tenure.values() if c.confidence == DISPUTED)
        )


@dataclass(frozen=True)
class SchemeRegistry:
    schemes: Mapping[str, ClassificationScheme]

    def get(self, scheme_id: str) -> ClassificationScheme:
        try:
            return self.schemes[scheme_id]
        except KeyError:
            raise UnknownScheme(
                f"no scheme {scheme_id!r} (known: {', '.join(sorted(self.schemes))})"
            ) from None

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.schemes))


def _tenure_from_data(entry: Mapping[str, object], scheme_id: str) -> TenureClass:
    for key in ("code", "label", "government", "transferable", "confidence", "source"):
        if key not in entry:
            raise ClassificationError(
                f"scheme {scheme_id!r}: tenure class missing {key!r}"
            )
    confidence = entry["confidence"]
    if confidence not in CONFIDENCE_LEVELS:
        raise ClassificationError(
            f"scheme {scheme_id!r}: confidence must be one of "
            f"{', '.join(sorted(CONFIDENCE_LEVELS))}, got {confidence!r}"
        )
    if not str(entry["source"]).strip():
        raise ClassificationError(
            f"scheme {scheme_id!r}: class {entry['code']!r} needs a non-empty source. "
            "An unattributed taxonomy is the same problem as an unattributed number."
        )
    return TenureClass(
        code=str(entry["code"]),
        label=str(entry["label"]),
        government=bool(entry["government"]),
        transferable=bool(entry["transferable"]),
        confidence=str(confidence),
        source=str(entry["source"]),
    )


def load_schemes(path: Path | str | None = None) -> SchemeRegistry:
    source = Path(path) if path is not None else DEFAULT_CLASSIFICATIONS_PATH
    with source.open(encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data.get("schemes")
    if not isinstance(entries, list) or not entries:
        raise ClassificationError(f"{source}: no schemes defined")
    schemes: dict[str, ClassificationScheme] = {}
    for entry in entries:
        scheme_id = str(entry["id"])
        tenure = {}
        for raw in entry.get("tenure_classes", []):
            klass = _tenure_from_data(raw, scheme_id)
            if klass.code in tenure:
                raise ClassificationError(
                    f"scheme {scheme_id!r}: duplicate tenure code {klass.code!r}"
                )
            tenure[klass.code] = klass
        if not tenure:
            raise ClassificationError(f"scheme {scheme_id!r}: no tenure classes")
        schemes[scheme_id] = ClassificationScheme(
            id=scheme_id,
            region=str(entry.get("region", "")),
            tenure=MappingProxyType(tenure),
            land_use=tuple(str(x) for x in entry.get("land_use_classes", [])),
            axis_notes=str(entry.get("axis_notes", "")),
            land_use_note=str(entry.get("land_use_note", "")),
        )
    return SchemeRegistry(MappingProxyType(schemes))


_DEFAULT_SCHEMES: SchemeRegistry | None = None


def default_schemes() -> SchemeRegistry:
    global _DEFAULT_SCHEMES
    if _DEFAULT_SCHEMES is None:
        _DEFAULT_SCHEMES = load_schemes()
    return _DEFAULT_SCHEMES
