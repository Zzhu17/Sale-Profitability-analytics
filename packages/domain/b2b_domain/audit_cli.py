import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from b2b_domain.audit import audit_workbook_template
from b2b_domain.d0 import EvidenceKind, load_canonical_csv_directory, run_d0_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the D0 readiness audit")
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--canonical-dir", type=Path)
    parser.add_argument(
        "--evidence-kind",
        choices=[kind.value for kind in EvidenceKind],
        default=EvidenceKind.SYNTHETIC,
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    template_issues = audit_workbook_template(args.template)
    result: dict[str, Any] = {
        "template": str(args.template),
        "template_status": "pass" if not template_issues else "fail",
        "template_issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "column": issue.column,
                "detail": issue.detail,
            }
            for issue in template_issues
        ],
    }
    if args.canonical_dir is None:
        result.update(
            {
                "d0_status": "Pending real anonymized data",
                "gates": {
                    name: {
                        "judgment": "Pending",
                        "evidence": "Real anonymized evidence has not been audited",
                    }
                    for name in (
                        "Customer 360",
                        "Profitability analytics",
                        "Reorder-cycle rules",
                        "Purchase-propensity ML",
                        "Temporal backtesting",
                    )
                },
            }
        )
    else:
        summary = run_d0_audit(
            load_canonical_csv_directory(args.canonical_dir),
            evidence_kind=EvidenceKind(args.evidence_kind),
        )
        result["d0"] = summary.to_dict()
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0 if not template_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
