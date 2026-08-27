"""Findings, rule contracts, and the engine that runs them.

Four things this module exists to enforce (AGENTS.md 3.2-3.4):

* **Every finding is typed, never boolean.** `UNVERIFIABLE` is a first-class output,
  not an error state, and arguably the product.

* **Flag, never verdict.** Nothing here decides that a record is wrong, fraudulent, or
  that title is defective. A finding says a rule fired, on which record, with what
  evidence. That is a legal constraint, not a style preference.

* **Rules are pure.** A rule receives a view — records, a derived index, and a unit
  registry — and returns findings. It reads no files, no config, no globals.

* **A rule that cannot run has not passed.** A rule whose witness is missing must
  return `UNVERIFIABLE`. A rule that *raises* has also not passed, so the engine can
  convert a crash into `UNVERIFIABLE` rather than let it read as silence.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Callable, Mapping, Protocol, Sequence, runtime_checkable

from kavach.records import EntityType, Index, RecordSet
from kavach.units import LadderRegistry

__all__ = [
    "Engine",
    "Reporter",
    "rule",
    "EngineResult",
    "Finding",
    "FindingClass",
    "OnRuleError",
    "Rule",
    "RuleScope",
    "SingleVersionView",
    "Subject",
    "VersionPairView",
]

VALIDATION_CLASSES = frozenset(range(1, 9))


class FindingClass(StrEnum):
    """AGENTS.md 3.3. The order is severity, not enum convenience."""

    CERTAIN_ERROR = "certain_error"
    """Grammar or conservation violated. No judgement involved."""

    CONFLICT = "conflict"
    """Two witnesses disagree. Precedence rule, else a human."""

    ANOMALY = "anomaly"
    """Statistical outlier. Directs sampling; never a finding on its own."""

    UNVERIFIABLE = "unverifiable"
    """No second witness exists. The rule abstained, and says so."""


class RuleScope(StrEnum):
    """Declared per rule. A rule that does not declare its scope does not run."""

    WITHIN_VERSION = "within_version"
    ACROSS_VERSION = "across_version"


class OnRuleError(StrEnum):
    RAISE = "raise"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class Subject:
    """What a finding localises to.

    HANDOFF_BUILD.md 5.2 measures whether the engine names the right *parcel*, not
    merely the right village, so this is typed rather than a free string.
    """

    entity_type: EntityType
    entity_id: str
    field_name: str | None = None
    display: str | None = None

    def __str__(self) -> str:
        label = self.display or self.entity_id
        if self.field_name:
            return f"{self.entity_type}:{label}.{self.field_name}"
        return f"{self.entity_type}:{label}"


@dataclass(frozen=True)
class Finding:
    """One rule firing on one record. Never a verdict."""

    rule_id: str
    validation_class: int
    finding_class: FindingClass
    subjects: tuple[Subject, ...]
    message: str
    evidence: Mapping[str, str] = field(default_factory=dict)
    as_of: dt.date | None = None
    missing_witness: str | None = None

    def __post_init__(self) -> None:
        if self.validation_class not in VALIDATION_CLASSES:
            raise ValueError(
                f"validation_class must be 1-8, got {self.validation_class}"
            )
        if not self.subjects:
            raise ValueError(
                f"{self.rule_id}: a finding must localise to at least one record. "
                "An unlocalised finding cannot be reviewed or measured."
            )
        if self.finding_class is FindingClass.UNVERIFIABLE and not self.missing_witness:
            raise ValueError(
                f"{self.rule_id}: an UNVERIFIABLE finding must name the witness it "
                "lacked. Abstaining without saying why is indistinguishable from "
                "passing."
            )
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))
        for key, value in self.evidence.items():
            if not isinstance(value, str):
                raise TypeError(
                    f"{self.rule_id}: evidence[{key!r}] must be a string. Values are "
                    "rendered exactly as recorded, so they are stringified by the "
                    "rule that knows their units."
                )

    @property
    def primary_subject(self) -> Subject:
        return self.subjects[0]

    @property
    def is_abstention(self) -> bool:
        return self.finding_class is FindingClass.UNVERIFIABLE

    def __str__(self) -> str:
        head = f"[{self.finding_class}] C{self.validation_class} {self.rule_id}"
        return f"{head} — {self.primary_subject}: {self.message}"


# --------------------------------------------------------------------------
# what a rule receives
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleVersionView:
    """Everything a WITHIN_VERSION rule is allowed to see.

    `index.unknown_*` holds records whose validity could not be determined. They are
    handed over deliberately: a rule that would have to guess about them must emit
    UNVERIFIABLE instead of quietly including or dropping them.
    """

    records: RecordSet
    index: Index
    registry: LadderRegistry
    as_of: dt.date | None = None

    @classmethod
    def of(
        cls,
        records: RecordSet,
        registry: LadderRegistry,
        as_of: dt.date | None = None,
    ) -> "SingleVersionView":
        return cls(records, records.index(as_of), registry, as_of)

    @property
    def ladder_id(self) -> str:
        return self.records.ladder_id


@dataclass(frozen=True)
class VersionPairView:
    """What an ACROSS_VERSION rule receives: the same mouza at two dates."""

    earlier: SingleVersionView
    later: SingleVersionView
    registry: LadderRegistry


@runtime_checkable
class Rule(Protocol):
    """`rule(view) -> findings`. No I/O, no globals, no config reads."""

    id: str
    validation_class: int
    scope: RuleScope

    def __call__(self, view) -> Sequence[Finding]: ...


# --------------------------------------------------------------------------
# the engine
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineResult:
    findings: tuple[Finding, ...]
    rules_run: tuple[str, ...]
    as_of: dt.date | None = None

    def of_class(self, finding_class: FindingClass) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.finding_class is finding_class)

    @property
    def certain_errors(self) -> tuple[Finding, ...]:
        return self.of_class(FindingClass.CERTAIN_ERROR)

    @property
    def abstentions(self) -> tuple[Finding, ...]:
        return self.of_class(FindingClass.UNVERIFIABLE)

    def by_validation_class(self) -> Mapping[int, int]:
        return MappingProxyType(dict(Counter(f.validation_class for f in self.findings)))

    def counts(self) -> Mapping[str, int]:
        return MappingProxyType(
            {fc.value: len(self.of_class(fc)) for fc in FindingClass}
        )

    def __len__(self) -> int:
        return len(self.findings)


@dataclass(frozen=True)
class Engine:
    """Runs rules and collects findings. Holds no state between runs.

    D1 and D5 (HANDOFF_BUILD.md 6.5) are this same object called twice — once for
    features, once as hard gates. There is never a second implementation.
    """

    rules: tuple[Rule, ...] = ()
    on_error: OnRuleError = OnRuleError.RAISE

    def __post_init__(self) -> None:
        seen = Counter(rule.id for rule in self.rules)
        duplicates = sorted(rule_id for rule_id, n in seen.items() if n > 1)
        if duplicates:
            raise ValueError(f"duplicate rule ids: {', '.join(duplicates)}")
        for rule in self.rules:
            if rule.validation_class not in VALIDATION_CLASSES:
                raise ValueError(
                    f"rule {rule.id!r} has validation_class {rule.validation_class}"
                )
            if not isinstance(rule.scope, RuleScope):
                raise ValueError(
                    f"rule {rule.id!r} must declare a RuleScope. A rule that does not "
                    "declare its scope does not run."
                )

    def run(
        self,
        records: RecordSet,
        registry: LadderRegistry,
        *,
        as_of: dt.date | None = None,
    ) -> EngineResult:
        view = SingleVersionView.of(records, registry, as_of)
        return self._run_views(
            {RuleScope.WITHIN_VERSION: view}, as_of=as_of
        )

    def run_pair(
        self,
        earlier: RecordSet,
        later: RecordSet,
        registry: LadderRegistry,
        *,
        earlier_as_of: dt.date | None = None,
        later_as_of: dt.date | None = None,
    ) -> EngineResult:
        earlier_view = SingleVersionView.of(earlier, registry, earlier_as_of)
        later_view = SingleVersionView.of(later, registry, later_as_of)
        return self._run_views(
            {
                RuleScope.WITHIN_VERSION: later_view,
                RuleScope.ACROSS_VERSION: VersionPairView(
                    earlier_view, later_view, registry
                ),
            },
            as_of=later_as_of,
        )

    def _run_views(self, views, *, as_of) -> EngineResult:
        findings: list[Finding] = []
        ran: list[str] = []
        for rule in self.rules:
            view = views.get(rule.scope)
            if view is None:
                # The caller did not supply what this rule's scope needs. That is
                # an abstention, not a pass.
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        validation_class=rule.validation_class,
                        finding_class=FindingClass.UNVERIFIABLE,
                        subjects=(
                            Subject(EntityType.MOUZA, "*", display="whole record set"),
                        ),
                        message=(
                            f"rule needs a {rule.scope} view, which this run did not "
                            "provide"
                        ),
                        missing_witness=str(rule.scope),
                        as_of=as_of,
                    )
                )
                continue
            ran.append(rule.id)
            try:
                findings.extend(rule(view))
            except Exception as exc:
                if self.on_error is OnRuleError.RAISE:
                    raise
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        validation_class=rule.validation_class,
                        finding_class=FindingClass.UNVERIFIABLE,
                        subjects=(
                            Subject(EntityType.MOUZA, "*", display="whole record set"),
                        ),
                        message=f"rule raised {type(exc).__name__}: {exc}",
                        missing_witness="rule did not complete",
                        as_of=as_of,
                    )
                )
        return EngineResult(tuple(findings), tuple(ran), as_of)


# --------------------------------------------------------------------------
# rule authoring
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Reporter:
    """Binds a rule's identity to the findings it emits.

    Rules never construct a `Finding` by hand. That keeps `rule_id`,
    `validation_class` and `as_of` consistent across every finding a rule
    produces, and makes it impossible to emit an abstention without naming the
    witness that was missing.
    """

    rule_id: str
    validation_class: int
    as_of: dt.date | None = None

    def _make(self, finding_class, subjects, message, evidence, missing_witness):
        if isinstance(subjects, Subject):
            subjects = (subjects,)
        return Finding(
            rule_id=self.rule_id,
            validation_class=self.validation_class,
            finding_class=finding_class,
            subjects=tuple(subjects),
            message=message,
            evidence=evidence or {},
            as_of=self.as_of,
            missing_witness=missing_witness,
        )

    def error(self, subjects, message, evidence=None) -> Finding:
        """Grammar or conservation violated. No judgement involved."""
        return self._make(FindingClass.CERTAIN_ERROR, subjects, message, evidence, None)

    def conflict(self, subjects, message, evidence=None) -> Finding:
        """Two witnesses disagree. Never a verdict about which is right."""
        return self._make(FindingClass.CONFLICT, subjects, message, evidence, None)

    def anomaly(self, subjects, message, evidence=None) -> Finding:
        """A statistical outlier. Directs sampling; never a finding alone."""
        return self._make(FindingClass.ANOMALY, subjects, message, evidence, None)

    def abstain(self, subjects, message, missing_witness, evidence=None) -> Finding:
        """The rule could not run. This is not a pass."""
        return self._make(
            FindingClass.UNVERIFIABLE, subjects, message, evidence, missing_witness
        )


@dataclass(frozen=True)
class _DeclaredRule:
    id: str
    validation_class: int
    scope: RuleScope
    fn: Callable
    description: str

    def __call__(self, view) -> list[Finding]:
        reporter = Reporter(
            self.id, self.validation_class, getattr(view, "as_of", None)
        )
        return list(self.fn(view, reporter) or ())


def rule(rule_id: str, validation_class: int, scope: RuleScope = RuleScope.WITHIN_VERSION):
    """Declare a pure rule.

    The decorated function receives `(view, report)` and may return or yield
    findings. Scope is mandatory and explicit — Ruling 2 — so that a rule can
    never quietly guess which version of a record it is looking at.
    """

    def wrap(fn: Callable) -> _DeclaredRule:
        if validation_class not in VALIDATION_CLASSES:
            raise ValueError(f"{rule_id}: validation_class must be 1-8")
        return _DeclaredRule(
            id=rule_id,
            validation_class=validation_class,
            scope=scope,
            fn=fn,
            description=(fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
        )

    return wrap
