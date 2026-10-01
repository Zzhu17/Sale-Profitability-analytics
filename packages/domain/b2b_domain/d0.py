import csv
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from statistics import mean, median
from typing import Any

from b2b_domain.audit import (
    AuditIssue,
    Severity,
    TableSpec,
    ValueState,
    audit_rows,
    decimal_value,
)
from b2b_domain.canonical import entity_match_candidates
from b2b_domain.source_adapters import RawScalar


class EvidenceKind(StrEnum):
    SYNTHETIC = "synthetic"
    REAL_ANONYMIZED = "real_anonymized"


class GateJudgment(StrEnum):
    PENDING = "Pending"
    PASS = "Pass"
    CONDITIONAL_PASS = "Conditional Pass"
    FAIL = "Fail"


@dataclass(frozen=True)
class GateResult:
    judgment: GateJudgment
    evidence: str


@dataclass(frozen=True)
class D0Summary:
    evidence_kind: EvidenceKind
    status: str
    issues: tuple[AuditIssue, ...]
    analyses: Mapping[str, Any]
    gates: Mapping[str, GateResult]
    provisional_decisions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_kind": self.evidence_kind,
            "status": self.status,
            "issues": [
                {
                    **asdict(issue),
                    "disposition": issue.disposition,
                }
                for issue in self.issues
            ],
            "analyses": self.analyses,
            "gates": {
                name: {"judgment": result.judgment, "evidence": result.evidence}
                for name, result in self.gates.items()
            },
            "provisional_decisions": self.provisional_decisions,
        }


CANDIDATE_SPECS: Mapping[str, TableSpec] = {
    "customers": TableSpec(
        "customers",
        frozenset({"customer_id", "customer_name"}),
        ("customer_id",),
        required_value_columns=("customer_id", "customer_name"),
    ),
    "products": TableSpec(
        "products",
        frozenset({"product_id", "product_name"}),
        ("product_id",),
        required_value_columns=("product_id", "product_name"),
    ),
    "invoices": TableSpec(
        "invoices",
        frozenset({"invoice_id", "customer_id", "order_date", "status", "total"}),
        ("invoice_id",),
        date_columns=("order_date",),
        decimal_columns=("total",),
        required_value_columns=("invoice_id", "customer_id", "order_date", "status", "total"),
    ),
    "invoice_items": TableSpec(
        "invoice_items",
        frozenset(
            {
                "line_id",
                "invoice_id",
                "product_id",
                "quantity",
                "unit_price",
                "unit_cost",
            }
        ),
        ("line_id",),
        decimal_columns=("quantity", "unit_price", "unit_cost", "reported_cogs"),
        positive_columns=("quantity",),
        required_value_columns=("line_id", "invoice_id", "product_id", "quantity", "unit_price"),
        warning_if_missing=(("unit_cost", "missing_cost"),),
    ),
    "returns": TableSpec(
        "returns",
        frozenset({"return_id", "customer_id", "product_id", "return_date", "quantity"}),
        ("return_id",),
        date_columns=("return_date",),
        decimal_columns=("quantity", "return_amount"),
        positive_columns=("quantity",),
        required_value_columns=(
            "return_id",
            "customer_id",
            "product_id",
            "return_date",
            "quantity",
        ),
    ),
    "inventory": TableSpec(
        "inventory",
        frozenset({"snapshot_date", "product_id", "on_hand"}),
        ("snapshot_date", "product_id"),
        date_columns=("snapshot_date",),
        decimal_columns=("on_hand",),
        required_value_columns=("snapshot_date", "product_id", "on_hand"),
    ),
}

PROVISIONAL_DECISIONS = (
    "source-to-canonical mappings",
    "purchase-event contract",
    "profitability contract v1",
    "label window",
    "eligibility rules",
    "return attribution rules",
    "inventory/product-affinity logic",
    "modeling feasibility",
)


def load_canonical_csv_directory(directory: Path) -> dict[str, list[dict[str, str]]]:
    tables: dict[str, list[dict[str, str]]] = {}
    for name in CANDIDATE_SPECS:
        path = directory / f"{name}.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as source:
            tables[name] = list(csv.DictReader(source))
    return tables


def _text(value: RawScalar) -> str:
    return "" if value is None else str(value).strip()


def _parsed_date(value: RawScalar) -> date | None:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        return None


def _issue(
    severity: Severity,
    code: str,
    table: str,
    row_number: int | None,
    column: str | None,
    detail: str,
) -> AuditIssue:
    return AuditIssue(severity, code, table, row_number, column, detail)


def _foreign_key_issues(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
    child_table: str,
    child_field: str,
    parent_table: str,
    parent_field: str,
) -> list[AuditIssue]:
    parent_ids = {_text(row.get(parent_field)) for row in tables.get(parent_table, ())}
    issues: list[AuditIssue] = []
    for row_number, row in enumerate(tables.get(child_table, ()), start=2):
        value = _text(row.get(child_field))
        if value and value not in parent_ids:
            issues.append(
                _issue(
                    Severity.CRITICAL,
                    "unmapped_required_entity",
                    child_table,
                    row_number,
                    child_field,
                    f"{value} is absent from {parent_table}.{parent_field}",
                )
            )
    return issues


def _entity_issues(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for table, id_field, name_field in (
        ("customers", "customer_id", "customer_name"),
        ("products", "product_id", "product_name"),
    ):
        candidates = entity_match_candidates(
            list(tables.get(table, ())), id_field=id_field, name_field=name_field
        )
        issues.extend(
            _issue(
                Severity.WARNING,
                "possible_duplicate_entity",
                table,
                None,
                name_field,
                (
                    f"{candidate.left_id} and {candidate.right_id}: "
                    f"combined={candidate.similarity:.4f}, "
                    f"edit={candidate.edit_similarity:.4f}, "
                    f"token={candidate.token_similarity:.4f}"
                ),
            )
            for candidate in candidates
        )
    return issues


def _cost_checks(
    rows: Sequence[Mapping[str, RawScalar]],
) -> tuple[list[AuditIssue], dict[str, int]]:
    issues: list[AuditIssue] = []
    coverage = {"missing": 0, "zero_or_negative": 0, "positive": 0, "invalid": 0}
    for row_number, row in enumerate(rows, start=2):
        state, unit_cost = decimal_value(row.get("unit_cost"))
        if state == ValueState.MISSING:
            coverage["missing"] += 1
            continue
        if state == ValueState.INVALID:
            coverage["invalid"] += 1
            continue
        assert unit_cost is not None
        if unit_cost <= 0:
            coverage["zero_or_negative"] += 1
            issues.append(
                _issue(
                    Severity.WARNING,
                    "nonpositive_cost",
                    "invoice_items",
                    row_number,
                    "unit_cost",
                    str(unit_cost),
                )
            )
        else:
            coverage["positive"] += 1
        quantity_state, quantity = decimal_value(row.get("quantity"))
        cogs_state, reported_cogs = decimal_value(row.get("reported_cogs"))
        if (
            quantity_state == ValueState.VALUE
            and cogs_state == ValueState.VALUE
            and quantity is not None
            and reported_cogs is not None
            and abs(quantity * unit_cost - reported_cogs) > Decimal("0.01")
        ):
            issues.append(
                _issue(
                    Severity.WARNING,
                    "cogs_reconciliation_mismatch",
                    "invoice_items",
                    row_number,
                    "reported_cogs",
                    "quantity × unit_cost differs from reported_cogs",
                )
            )
    return issues, coverage


def _inventory_checks(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
) -> tuple[list[AuditIssue], dict[str, Any]]:
    rows = tables.get("inventory", ())
    dates = sorted(
        parsed
        for row in rows
        if (parsed := _parsed_date(row.get("snapshot_date"))) is not None
    )
    if not dates:
        return [], {"coverage_start": None, "coverage_end": None, "missing_snapshots": None}
    start, end = dates[0], dates[-1]
    observed = {
        (_text(row.get("product_id")), parsed)
        for row in rows
        if (parsed := _parsed_date(row.get("snapshot_date"))) is not None
    }
    product_ids = {_text(row.get("product_id")) for row in tables.get("products", ())}
    missing: list[tuple[str, date]] = []
    current = start
    while current <= end:
        missing.extend(
            (product_id, current)
            for product_id in sorted(product_ids)
            if (product_id, current) not in observed
        )
        current += timedelta(days=1)
    issues = [
        _issue(
            Severity.WARNING,
            "inventory_gap",
            "inventory",
            None,
            "snapshot_date",
            f"Missing snapshot for {product_id} on {missing_date.isoformat()}",
        )
        for product_id, missing_date in missing
    ]
    return issues, {
        "coverage_start": start.isoformat(),
        "coverage_end": end.isoformat(),
        "missing_snapshots": len(missing),
    }


def _return_checks(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
) -> list[AuditIssue]:
    invoices = {
        _text(row.get("invoice_id")): row for row in tables.get("invoices", ())
    }
    invoice_ids = set(invoices)
    products_by_invoice: dict[str, set[str]] = defaultdict(set)
    for row in tables.get("invoice_items", ()):
        products_by_invoice[_text(row.get("invoice_id"))].add(
            _text(row.get("product_id"))
        )
    issues: list[AuditIssue] = []
    for row_number, row in enumerate(tables.get("returns", ()), start=2):
        invoice_id = _text(row.get("original_invoice_id"))
        if not invoice_id:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "unallocated_return",
                    "returns",
                    row_number,
                    "original_invoice_id",
                    "No original invoice link; inference was not fabricated",
                )
            )
            return_date = _parsed_date(row.get("return_date"))
            customer_id = _text(row.get("customer_id"))
            product_id = _text(row.get("product_id"))
            candidates = [
                candidate_id
                for candidate_id, invoice in invoices.items()
                if _text(invoice.get("customer_id")) == customer_id
                and product_id in products_by_invoice[candidate_id]
                and (invoice_date := _parsed_date(invoice.get("order_date"))) is not None
                and return_date is not None
                and invoice_date <= return_date
            ]
            if len(candidates) == 1:
                issues.append(
                    _issue(
                        Severity.INFORMATIONAL,
                        "return_inference_candidate",
                        "returns",
                        row_number,
                        "original_invoice_id",
                        f"Unique prior candidate {candidates[0]}; human review required",
                    )
                )
        elif invoice_id not in invoice_ids:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "unmatched_return_invoice",
                    "returns",
                    row_number,
                    "original_invoice_id",
                    invoice_id,
                )
            )
    return issues


def _status_checks(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
) -> list[AuditIssue]:
    invoice_status = {
        _text(row.get("invoice_id")): _text(row.get("status"))
        for row in tables.get("invoices", ())
    }
    issues: list[AuditIssue] = []
    for row_number, row in enumerate(tables.get("invoice_items", ()), start=2):
        status = invoice_status.get(_text(row.get("invoice_id")), "")
        if status.casefold() == "void":
            issues.append(
                _issue(
                    Severity.INFORMATIONAL,
                    "void_retained_line",
                    "invoice_items",
                    row_number,
                    "invoice_id",
                    "Void line was retained for status-semantics review and not counted as revenue",
                )
            )
    return issues


def _analyses(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
    cost_coverage: Mapping[str, int],
    inventory_coverage: Mapping[str, Any],
    today: date,
) -> dict[str, Any]:
    invoices = tables.get("invoices", ())
    customer_ids = {
        _text(row.get("customer_id")) for row in tables.get("customers", ())
    }
    valid_invoice_rows: list[Mapping[str, RawScalar]] = []
    for row in invoices:
        parsed_date = _parsed_date(row.get("order_date"))
        total_state, _ = decimal_value(row.get("total"))
        if (
            parsed_date is not None
            and parsed_date <= today
            and total_state == ValueState.VALUE
            and _text(row.get("customer_id")) in customer_ids
        ):
            valid_invoice_rows.append(row)
    customer_counts = Counter(
        _text(row.get("customer_id")) for row in valid_invoice_rows
    )
    buckets: Counter[str] = Counter()
    for count in customer_counts.values():
        if count == 1:
            label = "1"
        elif count == 2:
            label = "2"
        elif count <= 5:
            label = "3-5"
        elif count <= 10:
            label = "6-10"
        else:
            label = ">10"
        buckets[label] += 1
    status_counts = Counter(_text(row.get("status")) or "<unknown>" for row in invoices)
    invoice_status = {
        _text(row.get("invoice_id")): _text(row.get("status")) for row in invoices
    }
    void_line_count = 0
    for row in tables.get("invoice_items", ()):
        status = invoice_status.get(_text(row.get("invoice_id")), "")
        void_line_count += status.casefold() == "void"
    dates = sorted(
        parsed
        for row in valid_invoice_rows
        if (parsed := _parsed_date(row.get("order_date"))) is not None
    )
    customer_profiles: dict[str, Any] = {}
    invoice_customer = {
        _text(row.get("invoice_id")): _text(row.get("customer_id")) for row in invoices
    }
    products_by_customer: dict[str, Counter[str]] = defaultdict(Counter)
    for row in tables.get("invoice_items", ()):
        customer_id = invoice_customer.get(_text(row.get("invoice_id")), "")
        product_id = _text(row.get("product_id"))
        if customer_id and product_id:
            products_by_customer[customer_id][product_id] += 1
    return_counts = Counter(_text(row.get("customer_id")) for row in tables.get("returns", ()))
    raw_customer_counts = Counter(_text(row.get("customer_id")) for row in invoices)
    for customer_id in sorted(raw_customer_counts):
        customer_rows = [
            row
            for row in valid_invoice_rows
            if _text(row.get("customer_id")) == customer_id
        ]
        customer_dates = sorted(
            parsed
            for row in customer_rows
            if (parsed := _parsed_date(row.get("order_date"))) is not None
            and parsed <= today
        )
        gaps = [
            (right - left).days
            for left, right in zip(customer_dates, customer_dates[1:], strict=False)
        ]
        totals: list[Decimal] = []
        for row in customer_rows:
            total_state, total = decimal_value(row.get("total"))
            if total_state == ValueState.VALUE and total is not None:
                totals.append(total)
        customer_profiles[customer_id] = {
            "raw_invoice_row_count": raw_customer_counts[customer_id],
            "structurally_valid_invoice_row_count": len(customer_rows),
            "first_parseable_date": customer_dates[0].isoformat() if customer_dates else None,
            "last_parseable_date": customer_dates[-1].isoformat() if customer_dates else None,
            "active_months": len({value.strftime("%Y-%m") for value in customer_dates}),
            "adjacent_gap_days": gaps,
            "average_invoice_total": str(mean(totals)) if totals else None,
            "median_invoice_total": str(median(totals)) if totals else None,
            "top_products_by_line_count": products_by_customer[customer_id].most_common(5),
            "return_row_count": return_counts[customer_id],
            "adjacent_gaps_within_candidate_horizons": {
                str(horizon): sum(gap <= horizon for gap in gaps)
                for horizon in (14, 30, 60, 90)
            },
        }
    status_date_presence: dict[str, dict[str, int]] = {}
    for status, count in status_counts.items():
        status_rows = [
            row
            for row in invoices
            if (_text(row.get("status")) or "<unknown>") == status
        ]
        status_date_presence[status] = {
            "invoice_rows": count,
            "order_date_present": sum(bool(_text(row.get("order_date"))) for row in status_rows),
            "fulfillment_date_present": sum(
                bool(_text(row.get("fulfillment_date"))) for row in status_rows
            ),
            "payment_date_present": sum(
                bool(_text(row.get("payment_date"))) for row in status_rows
            ),
        }
    return_attribution: Counter[str] = Counter()
    invoice_ids = set(invoice_customer)
    for row in tables.get("returns", ()):
        invoice_id = _text(row.get("original_invoice_id"))
        if not invoice_id:
            return_attribution["unallocated"] += 1
        elif invoice_id in invoice_ids:
            return_attribution["exact"] += 1
        else:
            return_attribution["unmatched"] += 1
    temporal = {
        "first_parseable_event_date": dates[0].isoformat() if dates else None,
        "last_parseable_event_date": dates[-1].isoformat() if dates else None,
        "history_days": (dates[-1] - dates[0]).days + 1 if dates else None,
        "candidate_horizons": {
            str(horizon): {
                "latest_fully_observable_scoring_date": (
                    dates[-1] - timedelta(days=horizon)
                ).isoformat()
                if dates
                else None
            }
            for horizon in (14, 30, 60, 90)
        },
        "purchase_event_filter": "Pending real anonymized data",
    }
    return {
        "table_row_counts": {name: len(rows) for name, rows in tables.items()},
        "structurally_valid_invoice_rows_per_customer_buckets": dict(
            sorted(buckets.items())
        ),
        "customer_invoice_row_profiles": customer_profiles,
        "valid_purchase_distribution": "Pending purchase-event contract",
        "status_counts": dict(sorted(status_counts.items())),
        "status_date_presence": status_date_presence,
        "void_retained_line_count": void_line_count,
        "return_attribution": dict(return_attribution),
        "historical_cost_coverage": dict(cost_coverage),
        "inventory_coverage": dict(inventory_coverage),
        "temporal_feasibility": temporal,
    }


def _gate_results(
    evidence_kind: EvidenceKind, issues: Sequence[AuditIssue]
) -> Mapping[str, GateResult]:
    names = (
        "Customer 360",
        "Profitability analytics",
        "Reorder-cycle rules",
        "Purchase-propensity ML",
        "Temporal backtesting",
    )
    if evidence_kind != EvidenceKind.REAL_ANONYMIZED:
        return {
            name: GateResult(
                GateJudgment.PENDING,
                "Real anonymized evidence has not been audited",
            )
            for name in names
        }
    critical_count = sum(issue.severity == Severity.CRITICAL for issue in issues)
    warning_count = sum(issue.severity == Severity.WARNING for issue in issues)
    structural = (
        GateJudgment.FAIL
        if critical_count
        else GateJudgment.CONDITIONAL_PASS
        if warning_count
        else GateJudgment.PASS
    )
    return {
        "Customer 360": GateResult(structural, "Automated structural/entity checks"),
        "Profitability analytics": GateResult(
            structural,
            "Automated cost coverage and reconciliation; manual invoice sampling remains",
        ),
        "Reorder-cycle rules": GateResult(
            structural,
            "Automated timeline and status evidence; event contract remains a review decision",
        ),
        "Purchase-propensity ML": GateResult(
            GateJudgment.CONDITIONAL_PASS if not critical_count else GateJudgment.FAIL,
            "Manual label volume and leakage review is required",
        ),
        "Temporal backtesting": GateResult(
            GateJudgment.CONDITIONAL_PASS if not critical_count else GateJudgment.FAIL,
            "Expanding-window fold construction and positive counts require review",
        ),
    }


def run_d0_audit(
    tables: Mapping[str, Sequence[Mapping[str, RawScalar]]],
    *,
    evidence_kind: EvidenceKind,
    today: date | None = None,
) -> D0Summary:
    audit_date = today or date.today()
    issues: list[AuditIssue] = []
    for name, spec in CANDIDATE_SPECS.items():
        rows = tables.get(name)
        if rows is None:
            issues.append(
                _issue(Severity.CRITICAL, "missing_table", name, None, None, "Table is absent")
            )
            continue
        if not rows:
            issues.append(
                _issue(Severity.CRITICAL, "empty_table", name, None, None, "Table has no rows")
            )
            continue
        present_columns = {column for row in rows for column in row}
        issues.extend(
            _issue(
                Severity.CRITICAL,
                "missing_column",
                name,
                1,
                column,
                "Required column is absent",
            )
            for column in sorted(spec.required_columns - present_columns)
        )
        issues.extend(audit_rows(rows, spec, today=audit_date).issues)
    for args in (
        ("invoices", "customer_id", "customers", "customer_id"),
        ("invoice_items", "invoice_id", "invoices", "invoice_id"),
        ("invoice_items", "product_id", "products", "product_id"),
        ("returns", "customer_id", "customers", "customer_id"),
        ("returns", "product_id", "products", "product_id"),
        ("inventory", "product_id", "products", "product_id"),
    ):
        issues.extend(_foreign_key_issues(tables, *args))
    issues.extend(_entity_issues(tables))
    cost_issues, cost_coverage = _cost_checks(tables.get("invoice_items", ()))
    issues.extend(cost_issues)
    issues.extend(_return_checks(tables))
    issues.extend(_status_checks(tables))
    inventory_issues, inventory_coverage = _inventory_checks(tables)
    issues.extend(inventory_issues)
    analyses = _analyses(tables, cost_coverage, inventory_coverage, audit_date)
    status = (
        "Pending real anonymized data"
        if evidence_kind != EvidenceKind.REAL_ANONYMIZED
        else "D0 audit generated; manual contract review required"
    )
    return D0Summary(
        evidence_kind,
        status,
        tuple(issues),
        analyses,
        _gate_results(evidence_kind, issues),
        PROVISIONAL_DECISIONS,
    )
