import csv
from datetime import date
from pathlib import Path

from b2b_domain.audit import Disposition
from b2b_domain.d0 import EvidenceKind, GateJudgment, run_d0_audit

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"


def fixture_tables() -> dict[str, list[dict[str, str]]]:
    tables: dict[str, list[dict[str, str]]] = {}
    for path in FIXTURES.glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as source:
            tables[path.stem] = list(csv.DictReader(source))
    return tables


def test_d0_boundary_fixtures_cover_required_outcomes() -> None:
    summary = run_d0_audit(
        fixture_tables(), evidence_kind=EvidenceKind.SYNTHETIC, today=date(2026, 10, 1)
    )
    issues_by_code = {issue.code: issue for issue in summary.issues}

    assert {
        "duplicate_key",
        "void_retained_line",
        "missing_cost",
        "nonpositive_cost",
        "unmapped_required_entity",
        "unallocated_return",
        "return_inference_candidate",
        "inventory_gap",
        "future_date",
        "unparseable_date",
        "unparseable_decimal",
        "cogs_reconciliation_mismatch",
        "possible_duplicate_entity",
        "invalid_positive_value",
    } <= issues_by_code.keys()
    assert issues_by_code["duplicate_key"].disposition == Disposition.REJECT
    assert issues_by_code["missing_cost"].disposition == Disposition.QUARANTINE
    assert issues_by_code["void_retained_line"].disposition == Disposition.FLAG


def test_unknown_cost_and_zero_cost_are_counted_separately() -> None:
    summary = run_d0_audit(
        fixture_tables(), evidence_kind=EvidenceKind.SYNTHETIC, today=date(2026, 10, 1)
    )

    coverage = summary.analyses["historical_cost_coverage"]
    assert coverage["missing"] == 2
    assert coverage["zero_or_negative"] == 1
    assert coverage["positive"] == 2


def test_synthetic_evidence_cannot_complete_any_gate() -> None:
    summary = run_d0_audit(
        fixture_tables(), evidence_kind=EvidenceKind.SYNTHETIC, today=date(2026, 10, 1)
    )

    assert summary.status == "Pending real anonymized data"
    assert all(gate.judgment == GateJudgment.PENDING for gate in summary.gates.values())
    assert summary.analyses["inventory_coverage"]["missing_snapshots"] == 1
    assert summary.analyses["valid_purchase_distribution"] == "Pending purchase-event contract"
    assert summary.analyses["temporal_feasibility"]["history_days"] == 32
    customer_three = summary.analyses["customer_invoice_row_profiles"]["CUST-SYN-003"]
    assert customer_three["raw_invoice_row_count"] == 2
    assert customer_three["structurally_valid_invoice_row_count"] == 0
    assert customer_three["average_invoice_total"] is None
