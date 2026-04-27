from ai_scheduler import AIScheduleOutput, ScenarioInput, ScenarioTask, ScheduledTaskResult
from reliability_evaluator import (
    check_budget_limit,
    check_priority_inversion,
    compute_consistency_rate,
    evaluate_scenario_runs,
)


def _scenario(available_minutes: int = 30) -> ScenarioInput:
    return ScenarioInput(
        scenario_id="eval_case",
        owner_name="Alex",
        owner_email="alex@example.com",
        available_minutes=available_minutes,
        day_start_minutes=480,
        tasks=[
            ScenarioTask("t1", "Mochi", "Walk", 20, "high"),
            ScenarioTask("t2", "Mochi", "Feed", 15, "medium"),
        ],
    )


def _output(scheduled: list[ScheduledTaskResult], skipped: list[ScheduledTaskResult]) -> AIScheduleOutput:
    return AIScheduleOutput(
        scheduled=scheduled,
        skipped=skipped,
        warnings=[],
        rationale="Model output.",
    )


def test_budget_check_fails_when_scheduled_exceeds_budget():
    scenario = _scenario(available_minutes=20)
    output = _output(
        scheduled=[
            ScheduledTaskResult("t1", "Mochi", "Walk", 20, "high", None),
            ScheduledTaskResult("t2", "Mochi", "Feed", 15, "medium", None),
        ],
        skipped=[],
    )
    check = check_budget_limit(scenario, output)
    assert check.passed is False


def test_priority_inversion_check_fails_on_skipped_high():
    output = _output(
        scheduled=[ScheduledTaskResult("t2", "Mochi", "Feed", 15, "low", None)],
        skipped=[ScheduledTaskResult("t1", "Mochi", "Walk", 20, "high", None)],
    )
    check = check_priority_inversion(output)
    assert check.passed is False


def test_consistency_rate_detects_nonidentical_runs():
    run_a = _output(
        scheduled=[ScheduledTaskResult("t1", "Mochi", "Walk", 20, "high", None)],
        skipped=[ScheduledTaskResult("t2", "Mochi", "Feed", 15, "medium", None)],
    )
    run_b = _output(
        scheduled=[ScheduledTaskResult("t2", "Mochi", "Feed", 15, "medium", None)],
        skipped=[ScheduledTaskResult("t1", "Mochi", "Walk", 20, "high", None)],
    )
    assert compute_consistency_rate([run_a, run_b]) == 0.5


def test_evaluate_scenario_runs_passes_for_valid_output():
    scenario = _scenario(available_minutes=35)
    run = _output(
        scheduled=[
            ScheduledTaskResult("t1", "Mochi", "Walk", 20, "high", None),
            ScheduledTaskResult("t2", "Mochi", "Feed", 15, "medium", None),
        ],
        skipped=[],
    )
    evaluation = evaluate_scenario_runs(scenario, [run, run, run])
    assert evaluation.passed is True
    assert evaluation.compliance_rate == 1.0
