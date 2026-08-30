"""Build the reviewer's view of a real engine run.

HANDOFF_BUILD.md 7 step 3: the reviewer queue over real flags from step 2. This is
Layer E, not the Layer F dashboards AGENTS.md 8 warns off — no repository, no RBAC,
no APIs, and nothing here is mocked. Every figure comes from running the engine.

Three things this has to get right, all of them design decisions already settled:

* **Queue order is consequence, never ascending confidence** (HANDOFF_BUILD.md 6.6).
  Phase 1 has no model, so the uncertainty term does not exist yet and the page says
  so rather than inventing a score. Within a finding class, the queue orders by land
  at stake.

* **Abstentions are shown, not hidden.** `UNVERIFIABLE` is a first-class output. A
  reviewer UI that only listed errors would recreate the exact failure the project
  exists to attack.

* **Evidence, not verdicts.** Every row names the rule that fired and the record that
  disagrees, and nothing on the page asserts that a record is wrong.
"""

from __future__ import annotations

import datetime as dt
import json
from fractions import Fraction
from typing import Any, Mapping, Sequence

from kavach.classifications import SchemeRegistry, default_schemes
from kavach.findings import Engine, EngineResult, Finding, FindingClass
from kavach.records import EntityType, RecordSet
from kavach.rules import ALL_RULES
from kavach.rules.census import WITNESSES, witness_census
from kavach.units import Area, LadderRegistry, default_registry, format_area

__all__ = ["build_payload", "consequence_of", "queue_order"]

CLASS_TITLES: Mapping[int, str] = {
    1: "Grammar",
    2: "Conservation",
    3: "Completeness",
    4: "Chain continuity",
    5: "Text versus geometry",
    6: "Cross-system",
    7: "Statistical",
    8: "Witness census",
}

SEVERITY: Mapping[str, int] = {
    FindingClass.CERTAIN_ERROR.value: 0,
    FindingClass.CONFLICT.value: 1,
    FindingClass.ANOMALY.value: 2,
    FindingClass.UNVERIFIABLE.value: 3,
}


def consequence_of(finding: Finding, records: RecordSet, index) -> Fraction:
    """Land at stake, in the ladder's smallest unit.

    The consequence half of "consequence x uncertainty". The uncertainty half needs
    a calibrated model and does not exist in Phase 1, so this is not multiplied by
    anything and the page does not pretend otherwise.
    """
    total = Fraction(0)
    for subject in finding.subjects:
        if subject.entity_type is EntityType.KHESRA:
            khesra = index.khesra_by_id.get(subject.entity_id)
            if khesra is not None and khesra.area_stated is not None:
                total = total + khesra.area_stated.area.count
        elif subject.entity_type is EntityType.KHATA:
            khata = index.khata_by_id.get(subject.entity_id)
            if khata is not None and khata.area_stated is not None:
                total = total + khata.area_stated.area.count
        elif subject.entity_type is EntityType.HOLDING:
            for holding in index.holdings:
                if holding.id == subject.entity_id and holding.area_claimed:
                    total = total + holding.area_claimed.area.count
        elif subject.entity_type is EntityType.MOUZA:
            if records.mouza.area_stated is not None:
                total = total + records.mouza.area_stated.area.count
    return total


def queue_order(findings: Sequence[Finding], records: RecordSet, index):
    """Severity first, then land at stake. Never ascending confidence."""
    return sorted(
        findings,
        key=lambda f: (
            SEVERITY.get(f.finding_class.value, 9),
            -consequence_of(f, records, index),
            f.rule_id,
            f.primary_subject.entity_id,
        ),
    )


def _percent(part: int, whole: int) -> int:
    return (100 * part) // whole if whole else 0


def _finding_row(finding: Finding, records, index, registry) -> dict:
    stake = consequence_of(finding, records, index)
    ladder_id = records.mouza.ladder_id
    return {
        "rule_id": finding.rule_id,
        "validation_class": finding.validation_class,
        "class_title": CLASS_TITLES.get(finding.validation_class, "—"),
        "finding_class": finding.finding_class.value,
        "message": finding.message,
        "missing_witness": finding.missing_witness,
        "evidence": dict(finding.evidence),
        "subjects": [
            {
                "type": str(s.entity_type),
                "id": s.entity_id,
                "label": s.display or s.entity_id,
                "field": s.field_name,
            }
            for s in finding.subjects
        ],
        "primary": finding.primary_subject.display or finding.primary_subject.entity_id,
        "primary_id": finding.primary_subject.entity_id,
        "primary_type": str(finding.primary_subject.entity_type),
        "parcel_ids": [
            s.entity_id for s in finding.subjects
            if s.entity_type is EntityType.KHESRA
        ],
        "stake_units": str(stake),
        "stake_display": format_area(Area(ladder_id, stake), registry) if stake else "—",
    }


def _grouped(rows: list[dict]) -> list[dict]:
    """Findings collapsed by rule.

    Sixty-seven flat rows is a list nobody reads. Eleven rules, each with a count and
    the records under it, is a list somebody works through.
    """
    order: list[str] = []
    buckets: dict[str, dict] = {}
    for position, row in enumerate(rows):
        key = row["rule_id"]
        if key not in buckets:
            order.append(key)
            buckets[key] = {
                "rule_id": key,
                "validation_class": row["validation_class"],
                "class_title": row["class_title"],
                "finding_class": row["finding_class"],
                "message": row["message"],
                "rows": [],
            }
        buckets[key]["rows"].append(position)
    return [buckets[k] for k in order]


def _witness_rows(census) -> list[dict]:
    """Per-witness availability, with the inapplicable ones marked rather than zeroed.

    A witness that cannot exist for any parcel in the set — sub-plot areas, when
    every parcel is a leaf — is not available at 0 percent. It is not a question
    this record set can be asked, and showing it as a failed check would misread
    the shape of the register as a defect in it.
    """
    share_by_name = census.by_witness()
    rows = []
    for name, description in WITNESSES:
        applicable = sum(1 for p in census.parcels if name not in p.not_applicable)
        share = share_by_name.get(name)
        rows.append(
            {
                "name": name,
                "description": description,
                "applicable": applicable,
                "percent": (
                    (100 * share.numerator) // share.denominator
                    if share is not None
                    else None
                ),
            }
        )
    return rows


def _profile_comparison(registry, schemes) -> list[dict]:
    """Verifiability across the two record lineages and their reconciliation.

    EVIDENCE.md E8: khatian and jamabandi are independent witnesses to the same land.
    The gap between what either states alone and what they state together is the
    argument for the whole system, so the page shows it rather than describing it.
    """
    from kavach.synthetic import DocumentProfile, MouzaSpec, synthetic_mouza

    blurbs = {
        "khatian": "the older survey lineage — classification and shares, no per-holding areas",
        "jamabandi": "the de facto record of rights — per-holding areas, no shares, no classification",
        "combined": "both lineages reconciled against each other",
    }
    out = []
    for profile in DocumentProfile:
        records = synthetic_mouza(MouzaSpec(seed=11, profile=profile))
        rate = witness_census(records, registry, records.as_of).verifiability_rate
        out.append(
            {
                "profile": str(profile),
                "blurb": blurbs[str(profile)],
                "rate": str(rate) if rate is not None else None,
                "percent": (
                    (100 * rate.numerator) // rate.denominator
                    if rate is not None
                    else 0
                ),
            }
        )
    return out


def build_payload(
    records: RecordSet,
    *,
    registry: LadderRegistry | None = None,
    schemes: SchemeRegistry | None = None,
    engine: Engine | None = None,
    label: str = "",
) -> dict[str, Any]:
    """Everything the page needs, from one real engine run."""
    registry = registry or default_registry()
    schemes = schemes or default_schemes()
    engine = engine or Engine(ALL_RULES)

    as_of = records.as_of
    index = records.index(as_of)
    result: EngineResult = engine.run(records, registry, as_of=as_of, schemes=schemes)
    census = witness_census(records, registry, as_of)

    ordered = queue_order(result.findings, records, index)
    rows = [_finding_row(f, records, index, registry) for f in ordered]

    by_parcel: dict[str, list[int]] = {}
    errors_by_parcel: dict[str, list[int]] = {}
    for position, finding in enumerate(ordered):
        for subject in finding.subjects:
            if subject.entity_type is not EntityType.KHESRA:
                continue
            by_parcel.setdefault(subject.entity_id, []).append(position)
            if finding.finding_class is FindingClass.CERTAIN_ERROR:
                errors_by_parcel.setdefault(subject.entity_id, []).append(position)

    census_by_id = {p.khesra_id: p for p in census.parcels}
    parcels = []
    for khesra in index.leaves():
        entry = census_by_id.get(khesra.id)
        holdings = index.holdings_by_khesra.get(khesra.id, ())
        # The recorded raiyat, via khata. A jamabandi row carries a name, and a
        # reviewer navigates by it — showing khata ids alone would be unusable.
        holders = []
        for holding in holdings:
            khata = index.khata_by_id.get(holding.khata_id)
            if khata is None:
                continue
            for member in index.memberships_by_khata.get(khata.id, ()):
                owner = index.owner_by_id.get(member.owner_id)
                if owner is not None and owner.name_raw not in holders:
                    holders.append(owner.name_raw)
        parcels.append(
            {
                "id": khesra.id,
                "path": index.display_path(khesra.id) or khesra.local_number,
                "area": (
                    format_area(khesra.area_stated.area, registry)
                    if khesra.area_stated
                    else None
                ),
                "area_units": (
                    int(khesra.area_stated.area.count)
                    if khesra.area_stated and khesra.area_stated.area.is_integral
                    else 0
                ),
                "as_written": (
                    khesra.area_stated.as_written if khesra.area_stated else None
                ),
                "tenure": khesra.tenure,
                "khatas": sorted({h.khata_id for h in holdings}),
                "khata_numbers": sorted(
                    {
                        index.khata_by_id[h.khata_id].number
                        for h in holdings
                        if h.khata_id in index.khata_by_id
                    }
                ),
                "holders": holders,
                "witnesses_missing_labels": (
                    [n.replace("_", " ") for n in entry.absent] if entry else []
                ),
                "witnesses_present": list(entry.present) if entry else [],
                "witnesses_absent": list(entry.absent) if entry else [],
                "witnesses_na": list(entry.not_applicable) if entry else [],
                "witness_percent": (
                    _percent(entry.possible, entry.total) if entry else 0
                ),
                "finding_rows": by_parcel.get(khesra.id, []),
                "error_rows": errors_by_parcel.get(khesra.id, []),
            }
        )
    parcels.sort(
        key=lambda p: (-len(p["error_rows"]), -len(p["finding_rows"]),
                       p["witness_percent"], p["path"])
    )

    rate = census.verifiability_rate
    counts = result.counts()
    rules_by_class: dict[int, dict] = {}
    for declared in engine.rules:
        bucket = rules_by_class.setdefault(
            declared.validation_class,
            {
                "validation_class": declared.validation_class,
                "title": CLASS_TITLES.get(declared.validation_class, "—"),
                "rules": [],
            },
        )
        fired = sum(1 for f in result.findings if f.rule_id == declared.id)
        bucket["rules"].append(
            {
                "id": declared.id,
                "description": declared.description,
                "scope": str(declared.scope),
                "ran": declared.id in result.rules_run,
                "findings": fired,
            }
        )

    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "label": label or records.source,
        "mouza": {
            "id": records.mouza.id,
            "name": records.mouza.name,
            "district": records.mouza.district,
            "subdistrict": records.mouza.subdistrict,
            "subdistrict_term": records.mouza.subdistrict_term or "sub-district",
            "ladder": records.mouza.ladder_id,
            "as_of": str(as_of) if as_of else None,
            "source": records.source,
            "is_synthetic": records.source.startswith("synthetic:"),
            "total": (
                format_area(records.mouza.area_stated.area, registry)
                if records.mouza.area_stated
                else None
            ),
        },
        "totals": {
            "parcels": len(index.leaves()),
            "khatas": len(index.khatas),
            "owners": len(index.owners),
            "holdings": len(index.holdings),
            "findings": len(result),
            "certain_errors": counts[FindingClass.CERTAIN_ERROR.value],
            "conflicts": counts[FindingClass.CONFLICT.value],
            "anomalies": counts[FindingClass.ANOMALY.value],
            "unverifiable": counts[FindingClass.UNVERIFIABLE.value],
            "rules_registered": len(engine.rules),
            "rules_ran": len(result.rules_run),
        },
        "verifiability": {
            "rate": str(rate) if rate is not None else None,
            "percent": (
                (100 * rate.numerator) // rate.denominator if rate is not None else None
            ),
            "unexaminable": len(census.unexaminable),
            "witnesses": _witness_rows(census),
        },
        "profiles": _profile_comparison(registry, schemes),
        "groups": _grouped(rows),
        "queue": rows,
        "parcels": parcels,
        "rule_classes": [rules_by_class[k] for k in sorted(rules_by_class)],
    }
