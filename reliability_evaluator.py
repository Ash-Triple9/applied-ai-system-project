"""
reliability_evaluator.py
========================
Rule-compliance-first evaluation for AI schedule outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_scheduler import AIScheduleOutput, ScenarioInput
from pawpal_system import PRIORITY_ORDER


@dataclass(frozen=True)
class RuleCheck:
    name: str
    passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "details": self.details}


@dataclass(frozen=True)
class ScenarioEvaluation:
    scenario_id: str
    passed: bool
    compliance_rate: float
    consistency_rate: float
    checks: list[RuleCheck]
    scheduled_count: int
    skipped_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "passed": self.passed,
            "compliance_rate": self.compliance_rate,
            "consistency_rate": self.consistency_rate,
            "checks": [c.to_dict() for c in self.checks],
            "scheduled_count": self.scheduled_count,
            "skipped_count": self.skipped_count,
        }


def evaluate_scenario_runs(
    scenario: ScenarioInput,
    runs: list[AIScheduleOutput],
) -> ScenarioEvaluation:
    if not runs:
        raise ValueError("runs must contain at least one output")

    primary = runs[0]
    checks = [
        check_all_tasks_present(scenario, primary),
        check_no_duplicate_tasks(primary),
        check_budget_limit(scenario, primary),
        check_priority_inversion(primary),
        check_field_consistency(primary),
    ]
    passed_checks = sum(1 for c in checks if c.passed)
    compliance_rate = passed_checks / len(checks)

    consistency_rate = compute_consistency_rate(runs)
    passed = all(c.passed for c in checks)
    return ScenarioEvaluation(
        scenario_id=scenario.scenario_id,
        passed=passed,
        compliance_rate=round(compliance_rate, 4),
        consistency_rate=round(consistency_rate, 4),
        checks=checks,
        scheduled_count=len(primary.scheduled),
        skipped_count=len(primary.skipped),
    )


def check_all_tasks_present(scenario: ScenarioInput, output: AIScheduleOutput) -> RuleCheck:
    expected = {t.task_id for t in scenario.tasks}
    actual = {t.task_id for t in output.scheduled + output.skipped}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    passed = not missing and not extra
    details = "All task_ids present."
    if not passed:
        details = f"Missing={missing}, Extra={extra}"
    return RuleCheck("all_tasks_present", passed, details)


def check_no_duplicate_tasks(output: AIScheduleOutput) -> RuleCheck:
    ids = [t.task_id for t in output.scheduled + output.skipped]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    passed = len(duplicates) == 0
    details = "No duplicate task_ids."
    if duplicates:
        details = f"Duplicate task_ids found: {duplicates}"
    return RuleCheck("no_duplicate_tasks", passed, details)


def check_budget_limit(scenario: ScenarioInput, output: AIScheduleOutput) -> RuleCheck:
    used = sum(t.duration_minutes for t in output.scheduled)
    passed = used <= scenario.available_minutes
    details = f"Used={used}, Budget={scenario.available_minutes}"
    return RuleCheck("budget_limit", passed, details)


def check_priority_inversion(output: AIScheduleOutput) -> RuleCheck:
    if not output.scheduled or not output.skipped:
        return RuleCheck("priority_inversion", True, "No comparison needed.")

    scheduled_levels = [PRIORITY_ORDER.get(t.priority, 99) for t in output.scheduled]
    min_scheduled = min(scheduled_levels)
    violating = [
        t.task_id
        for t in output.skipped
        if PRIORITY_ORDER.get(t.priority, 99) < min_scheduled
    ]
    passed = len(violating) == 0
    details = "No priority inversion detected."
    if violating:
        details = f"Higher-priority skipped task_ids: {violating}"
    return RuleCheck("priority_inversion", passed, details)


def check_field_consistency(output: AIScheduleOutput) -> RuleCheck:
    bad_ids = []
    for task in output.scheduled + output.skipped:
        if not task.title.strip() or task.duration_minutes <= 0:
            bad_ids.append(task.task_id)
    passed = len(bad_ids) == 0
    details = "All task fields valid."
    if bad_ids:
        details = f"Invalid task payload fields for task_ids: {bad_ids}"
    return RuleCheck("field_consistency", passed, details)


def compute_consistency_rate(runs: list[AIScheduleOutput]) -> float:
    if len(runs) == 1:
        return 1.0

    # Agreement based on exact scheduled task_id ordering vs first run.
    baseline = tuple(t.task_id for t in runs[0].scheduled)
    matches = 0
    for output in runs:
        candidate = tuple(t.task_id for t in output.scheduled)
        if candidate == baseline:
            matches += 1
    return matches / len(runs)
