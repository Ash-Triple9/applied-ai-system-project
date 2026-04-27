"""
run_reliability.py
==================
CLI harness for AI reliability evaluation.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from ai_scheduler import AISchedulerAdapter, load_scenarios_from_json
from reliability_evaluator import evaluate_scenario_runs


def _markdown_report(
    eval_rows: list[dict[str, Any]],
    overall_pass: bool,
    compliance_rate: float,
    consistency_rate: float,
) -> str:
    lines = [
        "# PawPal+ Reliability Report",
        "",
        f"- Overall pass: **{'PASS' if overall_pass else 'FAIL'}**",
        f"- Aggregate compliance rate: **{compliance_rate:.2%}**",
        f"- Aggregate consistency rate: **{consistency_rate:.2%}**",
        "",
        "## Scenario Results",
        "",
    ]
    for row in eval_rows:
        lines.extend(
            [
                f"### {row['scenario_id']}",
                f"- Pass: {'PASS' if row['passed'] else 'FAIL'}",
                f"- Compliance: {row['compliance_rate']:.2%}",
                f"- Consistency: {row['consistency_rate']:.2%}",
                f"- Scheduled: {row['scheduled_count']}, Skipped: {row['skipped_count']}",
                "- Checks:",
            ]
        )
        for check in row["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            lines.append(f"  - {check['name']}: {status} ({check['details']})")
        lines.append("")
    return "\n".join(lines)


def run(
    scenarios_path: str,
    repeat_runs: int,
    compliance_threshold: float,
    output_dir: str,
) -> int:
    scenarios = load_scenarios_from_json(scenarios_path)
    adapter = AISchedulerAdapter()

    eval_rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        outputs = [adapter.generate_schedule(scenario) for _ in range(repeat_runs)]
        evaluation = evaluate_scenario_runs(scenario, outputs)
        eval_rows.append(evaluation.to_dict())

    scenario_passes = [row["passed"] for row in eval_rows]
    compliance_values = [float(row["compliance_rate"]) for row in eval_rows]
    consistency_values = [float(row["consistency_rate"]) for row in eval_rows]

    aggregate_compliance = sum(compliance_values) / len(compliance_values)
    aggregate_consistency = sum(consistency_values) / len(consistency_values)
    overall_pass = all(scenario_passes) and aggregate_compliance >= compliance_threshold

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / f"reliability_report_{timestamp}.json"
    md_path = output_path / f"reliability_report_{timestamp}.md"

    payload = {
        "generated_at_utc": timestamp,
        "repeat_runs": repeat_runs,
        "compliance_threshold": compliance_threshold,
        "overall_pass": overall_pass,
        "aggregate_compliance_rate": round(aggregate_compliance, 4),
        "aggregate_consistency_rate": round(aggregate_consistency, 4),
        "scenario_results": eval_rows,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(
            _markdown_report(
                eval_rows=eval_rows,
                overall_pass=overall_pass,
                compliance_rate=aggregate_compliance,
                consistency_rate=aggregate_consistency,
            )
        )

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(
        "Overall: "
        f"{'PASS' if overall_pass else 'FAIL'} | "
        f"Compliance={aggregate_compliance:.2%} | "
        f"Consistency={aggregate_consistency:.2%}"
    )
    return 0 if overall_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PawPal+ AI reliability evaluation.")
    parser.add_argument(
        "--scenarios",
        default="assets/curr_project_assets/reliability_scenarios.json",
        help="Path to reliability scenarios JSON file.",
    )
    parser.add_argument(
        "--repeat-runs",
        type=int,
        default=3,
        help="How many times to run AI scheduling per scenario.",
    )
    parser.add_argument(
        "--compliance-threshold",
        type=float,
        default=0.95,
        help="Minimum aggregate compliance rate required to pass.",
    )
    parser.add_argument(
        "--output-dir",
        default="assets/curr_project_assets/reports",
        help="Directory where reports are written.",
    )
    args = parser.parse_args()

    if args.repeat_runs <= 0:
        raise ValueError("--repeat-runs must be >= 1")
    if not 0.0 <= args.compliance_threshold <= 1.0:
        raise ValueError("--compliance-threshold must be between 0 and 1")

    return run(
        scenarios_path=args.scenarios,
        repeat_runs=args.repeat_runs,
        compliance_threshold=args.compliance_threshold,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
