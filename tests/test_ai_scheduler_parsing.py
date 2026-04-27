import json

import pytest

from ai_scheduler import (
    AIOutputParseError,
    AISchedulerAdapter,
    ScenarioInput,
    ScenarioTask,
)


def _scenario() -> ScenarioInput:
    return ScenarioInput(
        scenario_id="parse_case",
        owner_name="Casey",
        owner_email="casey@example.com",
        available_minutes=40,
        day_start_minutes=480,
        tasks=[
            ScenarioTask(
                task_id="a1",
                pet_name="Mochi",
                title="Walk",
                duration_minutes=20,
                priority="high",
            ),
            ScenarioTask(
                task_id="a2",
                pet_name="Mochi",
                title="Feed",
                duration_minutes=10,
                priority="medium",
            ),
        ],
    )


def test_adapter_rejects_unknown_task_id():
    def bad_model(_payload):
        return json.dumps(
            {
                "scheduled": [
                    {
                        "task_id": "a1",
                        "pet_name": "Mochi",
                        "title": "Walk",
                        "duration_minutes": 20,
                        "priority": "high",
                    }
                ],
                "skipped": [
                    {
                        "task_id": "unknown",
                        "pet_name": "Mochi",
                        "title": "Feed",
                        "duration_minutes": 10,
                        "priority": "medium",
                    }
                ],
                "warnings": [],
                "rationale": "test",
            }
        )

    adapter = AISchedulerAdapter(model_fn=bad_model, max_retries=0)
    with pytest.raises(AIOutputParseError, match="Unknown task_id"):
        adapter.generate_schedule(_scenario())


def test_adapter_rejects_missing_tasks():
    def bad_model(_payload):
        return json.dumps(
            {
                "scheduled": [
                    {
                        "task_id": "a1",
                        "pet_name": "Mochi",
                        "title": "Walk",
                        "duration_minutes": 20,
                        "priority": "high",
                    }
                ],
                "skipped": [],
                "warnings": [],
                "rationale": "test",
            }
        )

    adapter = AISchedulerAdapter(model_fn=bad_model, max_retries=0)
    with pytest.raises(AIOutputParseError, match="omitted tasks"):
        adapter.generate_schedule(_scenario())


def test_adapter_default_model_generates_complete_output():
    adapter = AISchedulerAdapter()
    output = adapter.generate_schedule(_scenario())
    all_ids = {t.task_id for t in output.scheduled + output.skipped}
    assert all_ids == {"a1", "a2"}
    assert output.rationale
