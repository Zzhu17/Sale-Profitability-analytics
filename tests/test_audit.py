from datetime import date
from pathlib import Path

from b2b_domain.audit import TableSpec, audit_csv, audit_workbook_template

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"
TEMPLATE = (
    Path(__file__).parents[1]
    / "data"
    / "templates"
    / "Resume_Project_03_Sample_Data_Template.xlsx"
)


def test_audit_csv_surfaces_critical_source_defects() -> None:
    spec = TableSpec(
        name="invoices",
        required_columns=frozenset(
            {"invoice_id", "customer_id", "order_date", "status", "total"}
        ),
        key_columns=("invoice_id",),
        date_columns=("order_date",),
        decimal_columns=("total",),
    )

    result = audit_csv(FIXTURES / "invoices.csv", spec, today=date(2026, 10, 1))

    assert result.row_count == 5
    assert {issue.code for issue in result.issues} == {
        "future_date",
        "unparseable_date",
        "unparseable_decimal",
    }


def test_workbook_guide_contains_expected_sheets() -> None:
    assert audit_workbook_template(TEMPLATE) == ()
