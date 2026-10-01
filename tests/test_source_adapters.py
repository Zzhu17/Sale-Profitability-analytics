from io import BytesIO
from pathlib import Path

from b2b_domain.canonical import CanonicalEntity, SourceMapping, map_record
from b2b_domain.ingestion import safe_filename, stage_source
from b2b_domain.source_adapters import CsvSourceAdapter, ExcelSourceAdapter, RawRecord

TEMPLATE = (
    Path(__file__).parents[1]
    / "data"
    / "templates"
    / "Resume_Project_03_Sample_Data_Template.xlsx"
)


def test_csv_adapter_preserves_unknown_separately_from_zero(tmp_path: Path) -> None:
    source = tmp_path / "values.csv"
    source.write_text("id,amount\nA,\nB,0\n", encoding="utf-8")

    records = list(CsvSourceAdapter(source).records())

    assert records[0].values["amount"] == ""
    assert records[1].values["amount"] == "0"
    assert [record.original_row_number for record in records] == [2, 3]


def test_excel_adapter_uses_configured_sheet_and_real_row_number() -> None:
    records = list(
        ExcelSourceAdapter(
            TEMPLATE,
            header_rows={"Invoices": 4},
            included_sheets=frozenset({"Invoices"}),
        ).records()
    )

    assert records[0].source_name == "Invoices"
    assert records[0].original_row_number == 5
    assert "invoice_id" in records[0].values


def test_mapping_is_separate_from_raw_adapter() -> None:
    raw = RawRecord("customer_export", 8, {"Customer ID": "C1", "Name": "Acme"})
    mapping = SourceMapping(
        "customer_export",
        CanonicalEntity.CUSTOMERS,
        {"Customer ID": "customer_id", "Name": "customer_name"},
    )

    canonical = map_record(raw, mapping)

    assert canonical.values == {"customer_id": "C1", "customer_name": "Acme"}
    assert canonical.original_row_number == 8


def test_staging_hashes_bytes_and_sanitizes_filename(tmp_path: Path) -> None:
    staged = stage_source(BytesIO(b"id,value\n1,0\n"), "../source export.csv", tmp_path)

    assert staged.original_filename == "source_export.csv"
    assert len(staged.sha256) == 64
    assert staged.path.read_bytes() == b"id,value\n1,0\n"


def test_safe_filename_rejects_unsupported_sources() -> None:
    try:
        safe_filename("source.xls")
    except ValueError as error:
        assert "CSV, XLSX, or XLSM" in str(error)
    else:
        raise AssertionError("Unsupported source type was accepted")
