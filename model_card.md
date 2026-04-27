# Model Card: PawPal+ Reliability Extension

## 1) System Overview
**Project name:** PawPal+ Reliability Extension  
**Base project:** PawPal+ (Modules 1-3)  
**Base project summary:** PawPal+ is a Python + Streamlit pet-care scheduling assistant that helps owners manage tasks across pets using time budget, priority, and recurrence rules. It generates daily schedules, flags conflicts, and provides human-readable plan explanations.

This extension adds an AI-style scheduling adapter and a reliability evaluation harness that measures compliance and consistency across repeated runs.

## 2) Intended Use
- Help pet owners generate and evaluate daily care schedules.
- Demonstrate applied AI engineering patterns: structured outputs, validation, and reliability testing.
- Support local experimentation and portfolio demonstration.

## 3) Out-of-Scope / Not Intended
- Medical or emergency decision-making for pets.
- Autonomous real-world task execution.
- Guarantees of optimal schedules under all constraints.
- Production deployment without additional security, monitoring, and human oversight.

## 4) Model / AI Behavior Description
The system uses an adapter interface (`AISchedulerAdapter`) that enforces strict structured output:
- `scheduled`
- `skipped`
- `warnings`
- `rationale`

Current default behavior uses a deterministic baseline scheduler through the adapter interface, which enables reliable testing and reproducibility while preserving a model-like contract for future hosted LLM integration.

## 5) Data and Scenario Inputs
Reliability testing uses predefined scenario inputs with:
- owner profile and time budget
- day start time
- task metadata (priority, duration, frequency, preferred time)

Scenarios are stored in:
- `assets/curr_project_assets/reliability_scenarios.json`

## 6) Reliability / Evaluation Approach
The evaluator runs repeated trials and computes:
- **Rule compliance** (primary gate)
- **Consistency rate** across repeated outputs (secondary metric)

Current rule checks include:
- all tasks accounted for
- no duplicate task IDs
- budget limit compliance
- priority inversion detection
- field consistency validation

Outputs are exported as JSON + Markdown reports for traceability.

## 7) Known Limitations
- Default adapter path is deterministic; it does not yet represent variability of hosted LLMs.
- Scenario coverage is finite and may miss uncommon edge cases.
- Evaluation emphasizes structural correctness over deeper semantic quality.
- Results depend on task metadata quality (garbage in, garbage out).

## 8) Bias and Fairness Considerations
Potential bias sources:
- Scenario/task definitions may reflect a narrow set of owner routines.
- Priority and duration assumptions may encode subjective household preferences.

Mitigations in current version:
- Explicit rule-based checks reduce arbitrary behavior.
- Human reviewer loop is included for failed/borderline outputs.
- Transparent report artifacts allow manual inspection and revision of criteria.

## 9) Misuse Risks and Safeguards
Potential misuse:
- Treating output as authoritative without human review.
- Using tool suggestions beyond intended non-critical planning contexts.

Safeguards:
- Clear non-medical/non-emergency scope.
- Guardrail and compliance checks before pass/fail.
- Reported warnings and skipped tasks surfaced to the user.
- Recommendation for human review of borderline/failed cases.

## 10) AI Collaboration Reflection
I used AI assistance for implementation planning, test case generation, and debugging edge conditions in scheduling and evaluation.

- **Helpful AI suggestion:** enforce a strict output schema (`scheduled`, `skipped`, `warnings`, `rationale`) and reject malformed output early. This improved safety and testability.
- **Flawed AI suggestion:** treat consistency as the primary pass/fail gate. I corrected this by making rule compliance primary and consistency secondary, preventing consistently wrong outputs from passing.

## 11) Testing Summary
- Unit tests cover scheduler behavior, parser strictness, and evaluator checks.
- Reliability harness runs multiple scenarios and writes pass/fail summaries.
- Current project evidence shows stable, reproducible outputs on included scenarios.

## 12) Future Improvements
- Plug in a real hosted LLM behind the existing adapter.
- Add adversarial and long-horizon scenarios.
- Expand semantic quality checks beyond structural/task-level correctness.
- Add CI gating on reliability thresholds to block regressions.