"""
ai_scheduler.py
===============
AI scheduling adapter for PawPal+ with strict output parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Optional

from pawpal_system import Owner, Pet, Scheduler, Task, VALID_FREQUENCIES, VALID_PRIORITIES


@dataclass(frozen=True)
class ScenarioTask:
    task_id: str
    pet_name: str
    title: str
    duration_minutes: int
    priority: str
    frequency: str = "daily"
    preferred_time: Optional[str] = None


@dataclass(frozen=True)
class ScenarioInput:
    scenario_id: str
    owner_name: str
    owner_email: str
    available_minutes: int
    day_start_minutes: int
    tasks: list[ScenarioTask]


@dataclass(frozen=True)
class ScheduledTaskResult:
    task_id: str
    pet_name: str
    title: str
    duration_minutes: int
    priority: str
    preferred_time: Optional[str]


@dataclass(frozen=True)
class AIScheduleOutput:
    scheduled: list[ScheduledTaskResult]
    skipped: list[ScheduledTaskResult]
    warnings: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        def serialize_task(t: ScheduledTaskResult) -> dict[str, Any]:
            return {
                "task_id": t.task_id,
                "pet_name": t.pet_name,
                "title": t.title,
                "duration_minutes": t.duration_minutes,
                "priority": t.priority,
                "preferred_time": t.preferred_time,
            }

        return {
            "scheduled": [serialize_task(t) for t in self.scheduled],
            "skipped": [serialize_task(t) for t in self.skipped],
            "warnings": list(self.warnings),
            "rationale": self.rationale,
        }


class AIOutputParseError(ValueError):
    """Raised when model output cannot be parsed into required schema."""


ModelCallable = Callable[[dict[str, Any]], str]


def load_scenarios_from_json(path: str) -> list[ScenarioInput]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios: list[ScenarioInput] = []
    for raw in data["scenarios"]:
        scenario_id = str(raw["scenario_id"])
        owner = raw["owner"]
        day_start_minutes = int(raw.get("day_start_minutes", 480))

        tasks: list[ScenarioTask] = []
        for task_raw in raw["tasks"]:
            tasks.append(
                ScenarioTask(
                    task_id=str(task_raw["task_id"]),
                    pet_name=str(task_raw["pet_name"]),
                    title=str(task_raw["title"]),
                    duration_minutes=int(task_raw["duration_minutes"]),
                    priority=str(task_raw["priority"]),
                    frequency=str(task_raw.get("frequency", "daily")),
                    preferred_time=task_raw.get("preferred_time"),
                )
            )

        scenarios.append(
            ScenarioInput(
                scenario_id=scenario_id,
                owner_name=str(owner["name"]),
                owner_email=str(owner["email"]),
                available_minutes=int(owner["available_minutes"]),
                day_start_minutes=day_start_minutes,
                tasks=tasks,
            )
        )
    return scenarios


def scenario_to_owner(scenario: ScenarioInput) -> Owner:
    owner = Owner(
        name=scenario.owner_name,
        email=scenario.owner_email,
        available_minutes=scenario.available_minutes,
    )
    pets: dict[str, Pet] = {}
    for task in scenario.tasks:
        if task.priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority in scenario: {task.priority!r}")
        if task.frequency not in VALID_FREQUENCIES:
            raise ValueError(f"Invalid frequency in scenario: {task.frequency!r}")

        pet = pets.get(task.pet_name)
        if pet is None:
            pet = Pet(name=task.pet_name, species="unknown")
            pets[task.pet_name] = pet
            owner.add_pet(pet)

        task_obj = Task(
            title=task.title,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            frequency=task.frequency,
            preferred_time=task.preferred_time,
        )
        # Keep stable lookup id for strict parsing checks.
        setattr(task_obj, "task_id", task.task_id)
        pet.add_task(task_obj)
    return owner


def _task_to_result(task: Task) -> ScheduledTaskResult:
    task_id = getattr(task, "task_id", None)
    if task_id is None:
        raise AIOutputParseError(f"Task missing task_id: {task.title!r}")
    return ScheduledTaskResult(
        task_id=str(task_id),
        pet_name=task.pet_name or "",
        title=task.title,
        duration_minutes=task.duration_minutes,
        priority=task.priority,
        preferred_time=task.preferred_time,
    )


def baseline_schedule_output(scenario: ScenarioInput) -> AIScheduleOutput:
    owner = scenario_to_owner(scenario)
    scheduler = Scheduler(owner=owner, day_start_minutes=scenario.day_start_minutes)
    scheduler.build_schedule()
    return AIScheduleOutput(
        scheduled=[_task_to_result(t) for t in scheduler.scheduled_tasks],
        skipped=[_task_to_result(t) for t in scheduler.skipped_tasks],
        warnings=list(scheduler.conflicts),
        rationale="Generated by baseline greedy scheduler.",
    )


class AISchedulerAdapter:
    """
    Adapter that prompts a model and strictly validates returned schedule JSON.
    """

    def __init__(
        self,
        model_fn: Optional[ModelCallable] = None,
        max_retries: int = 2,
    ) -> None:
        self.model_fn = model_fn or self._default_model_fn
        self.max_retries = max_retries

    def generate_schedule(self, scenario: ScenarioInput) -> AIScheduleOutput:
        payload = self._build_payload(scenario)
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            raw = self.model_fn(payload)
            try:
                return self._parse_output(raw, scenario)
            except (json.JSONDecodeError, KeyError, TypeError, AIOutputParseError) as exc:
                last_error = exc
        raise AIOutputParseError(f"Failed to parse model output after retries: {last_error}")

    @staticmethod
    def _build_payload(scenario: ScenarioInput) -> dict[str, Any]:
        return {
            "scenario_id": scenario.scenario_id,
            "owner": {
                "name": scenario.owner_name,
                "email": scenario.owner_email,
                "available_minutes": scenario.available_minutes,
            },
            "day_start_minutes": scenario.day_start_minutes,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "pet_name": t.pet_name,
                    "title": t.title,
                    "duration_minutes": t.duration_minutes,
                    "priority": t.priority,
                    "frequency": t.frequency,
                    "preferred_time": t.preferred_time,
                }
                for t in scenario.tasks
            ],
            "expected_output_format": {
                "scheduled": ["task_id", "pet_name", "title", "duration_minutes", "priority"],
                "skipped": ["task_id", "pet_name", "title", "duration_minutes", "priority"],
                "warnings": "string[]",
                "rationale": "string",
            },
        }

    @staticmethod
    def _parse_output(raw: str, scenario: ScenarioInput) -> AIScheduleOutput:
        payload = json.loads(raw)
        allowed_ids = {t.task_id for t in scenario.tasks}
        seen_ids: set[str] = set()

        def parse_task_list(items: Any, list_name: str) -> list[ScheduledTaskResult]:
            if not isinstance(items, list):
                raise AIOutputParseError(f"{list_name} must be a list")
            parsed: list[ScheduledTaskResult] = []
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    raise AIOutputParseError(f"{list_name}[{idx}] must be an object")
                task_id = str(item["task_id"])
                if task_id not in allowed_ids:
                    raise AIOutputParseError(f"Unknown task_id {task_id!r} in {list_name}")
                if task_id in seen_ids:
                    raise AIOutputParseError(f"Duplicate task_id {task_id!r} across output lists")
                seen_ids.add(task_id)
                parsed.append(
                    ScheduledTaskResult(
                        task_id=task_id,
                        pet_name=str(item["pet_name"]),
                        title=str(item["title"]),
                        duration_minutes=int(item["duration_minutes"]),
                        priority=str(item["priority"]),
                        preferred_time=item.get("preferred_time"),
                    )
                )
            return parsed

        scheduled = parse_task_list(payload["scheduled"], "scheduled")
        skipped = parse_task_list(payload["skipped"], "skipped")
        warnings = payload.get("warnings", [])
        rationale = payload.get("rationale", "")

        if not isinstance(warnings, list) or not all(isinstance(w, str) for w in warnings):
            raise AIOutputParseError("warnings must be a list[str]")
        if not isinstance(rationale, str) or not rationale.strip():
            raise AIOutputParseError("rationale must be a non-empty string")

        if len(seen_ids) != len(allowed_ids):
            missing = sorted(allowed_ids - seen_ids)
            raise AIOutputParseError(f"Model output omitted tasks: {missing}")

        return AIScheduleOutput(
            scheduled=scheduled,
            skipped=skipped,
            warnings=warnings,
            rationale=rationale.strip(),
        )

    @staticmethod
    def _default_model_fn(payload: dict[str, Any]) -> str:
        # Default model path uses baseline scheduler behavior while preserving
        # a model-like JSON interface for integration and testing.
        scenario = ScenarioInput(
            scenario_id=str(payload["scenario_id"]),
            owner_name=str(payload["owner"]["name"]),
            owner_email=str(payload["owner"]["email"]),
            available_minutes=int(payload["owner"]["available_minutes"]),
            day_start_minutes=int(payload["day_start_minutes"]),
            tasks=[
                ScenarioTask(
                    task_id=str(t["task_id"]),
                    pet_name=str(t["pet_name"]),
                    title=str(t["title"]),
                    duration_minutes=int(t["duration_minutes"]),
                    priority=str(t["priority"]),
                    frequency=str(t.get("frequency", "daily")),
                    preferred_time=t.get("preferred_time"),
                )
                for t in payload["tasks"]
            ],
        )
        result = baseline_schedule_output(scenario)
        return json.dumps(result.to_dict())
