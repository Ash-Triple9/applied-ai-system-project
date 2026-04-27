# PawPal+ Reliability Extension

# Loom Link:
https://www.loom.com/share/187add2f2dd148e29ee976e250baf47f 

## Original Project (Modules 1-3): PawPal+
My original Modules 1-3 project is **PawPal+**, a Python + Streamlit pet-care scheduling assistant. Its goal was to help pet owners enter owner/pet/task details and generate a practical daily care plan based on time budget, task priority, and recurrence (daily/weekly/as-needed). The system also explained scheduling decisions and flagged conflicts such as overlapping preferred times or priority inversions.

## Title and Summary
**PawPal+ Reliability Extension** adds an AI-reliability testing layer to the original scheduling system so outputs can be evaluated for consistency and quality, not just generated. This matters because AI-assisted planning tools must be trustworthy: users need confidence that the same scenario yields stable, policy-aligned results and that failures are visible through measurable test outcomes.

## Architecture Overview
The system architecture now has three logical layers:

1. **Test Inputs Layer** — scenario data (owner, pet, task configurations) and prompt/evaluation criteria are prepared.
2. **AI Scheduling Layer** — an AI model/agent produces schedule outputs and explanations from the provided inputs.
3. **Reliability Testing Layer** — a tester script runs repeated trials, compares outputs for consistency and rule compliance, computes reliability metrics (e.g., consistency score, pass rate), and emits a pass/fail result.

A **human reviewer** sits after automated evaluation to review failed or borderline cases and feed improved criteria back into prompt/test design. This creates a feedback loop that steadily improves reliability over time.

Diagram file: `assets/curr_project_assets/system_testing_diagram.mmd`  
Rendered image: `assets/curr_project_assets/system_testing_diagram.png`

## Setup Instructions
1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the original scheduler tests:
   ```bash
   python3 -m pytest tests/test_pawpal.py -v
   ```
4. Run all tests (including AI reliability tests):
   ```bash
   python3 -m pytest -q
   ```
5. Run the reliability harness:
   ```bash
   python3 run_reliability.py --repeat-runs 3 --compliance-threshold 0.95
   ```
6. (Optional) Run in browser:
   ```bash
   streamlit run app.py
   ```
   In the app, open **Section 5: AI Reliability Check**, run evaluation, then click
   **Export latest reliability report** to save report files from the UI.
7. Open generated reports:
   - JSON: `assets/curr_project_assets/reports/reliability_report_<timestamp>.json`
   - Markdown: `assets/curr_project_assets/reports/reliability_report_<timestamp>.md`

## Sample Interactions
### Example 1: End-to-end reliability run
**Input command**
```bash
python3 run_reliability.py --repeat-runs 3 --compliance-threshold 0.95
```
**Output (from latest run)**
- Overall: `PASS`
- Aggregate compliance: `100.00%`
- Aggregate consistency: `100.00%`
- Reports written to:
  - `assets/curr_project_assets/reports/reliability_report_20260425T222729Z.json`
  - `assets/curr_project_assets/reports/reliability_report_20260425T222729Z.md`

### Example 1b: In-browser reliability + export
**Input actions**
- Run `streamlit run app.py`
- In **Section 5**, set:
  - Repeated runs per scenario: `3`
  - Compliance threshold: `0.95`
- Click **Run reliability check**, then **Export latest reliability report**

**Output**
- UI shows overall PASS/FAIL with aggregate compliance and consistency.
- Export writes JSON + Markdown reports to:
  - `assets/curr_project_assets/reports/reliability_report_<timestamp>.json`
  - `assets/curr_project_assets/reports/reliability_report_<timestamp>.md`

### Example 2: Budget-constrained scenario behavior
**Scenario input**: `tight_budget_priority_tradeoff` with `available_minutes=35` and tasks totaling more than budget.  
**AI output summary**
- Scheduled: `2`
- Skipped: `1`
- Rule checks:
  - `budget_limit`: `PASS (Used=25, Budget=35)`
  - `priority_inversion`: `PASS`

### Example 3: Overlap scenario reliability checks
**Scenario input**: `overlap_detection_case` with overlapping preferred times included in task setup.  
**AI output summary**
- Scheduled: `3`
- Skipped: `0`
- Compliance checks: all pass
- Consistency across 3 repeated runs: `100.00%`

## Design Decisions
I implemented reliability as an additive layer around the existing PawPal+ scheduler instead of rewriting the app. The AI integration uses a strict schema contract (`scheduled`, `skipped`, `warnings`, `rationale`) so model outputs are parseable and fail fast when malformed.

The primary pass/fail gate is **rule compliance** (budget limits, complete task coverage, duplicate prevention, priority inversion detection), while **consistency across repeated runs** is tracked as a secondary metric. This trade-off favors safety and correctness first, then stability.

I also kept a baseline path via the deterministic scheduler as the default model adapter implementation. This gives a reliable reference for future external-model integration while preserving reproducibility during development.

To make adoption easier, I implemented reliability in both interfaces: CLI (`run_reliability.py`) for automation/CI and Streamlit UI (`app.py`, Section 5) for interactive review and one-click report export.

## Testing Summary
### What worked
- `33` tests pass (`python3 -m pytest -q`), including:
  - legacy scheduler tests in `tests/test_pawpal.py`
  - new parser tests in `tests/test_ai_scheduler_parsing.py`
  - new evaluator tests in `tests/test_reliability_evaluator.py`
- Reliability runner generates both JSON and Markdown reports and exits successfully when threshold conditions are met.
- Streamlit UI reliability flow works end-to-end, including the report export button.

### What did not work (or is intentionally deferred)
- The current AI adapter defaults to a deterministic baseline model function rather than a hosted external LLM API. This was intentional to ensure stable development and verifiable reliability checks before adding networked model dependencies.
- A previous deprecation warning in UTC timestamp generation was fixed by switching to timezone-aware `datetime.now(UTC)`.

### What I learned from testing
- Defining explicit output contracts early makes AI integration significantly safer.
- Rule-level checks catch practical failures that simple “did it run?” checks miss.
- Repeated-run consistency is easy to add once outputs are normalized to task IDs.

## Reflection
This project reinforced that AI systems are not just about generating outputs; they are about building guardrails that make those outputs dependable. I learned to separate generation from evaluation and treat reliability as a first-class engineering concern.

From a problem-solving perspective, the most effective strategy was incremental layering: keep the deterministic baseline intact, add strict contracts, then add automated evaluation and reporting. That approach reduced risk and made each step testable.

For future work, I would integrate a real LLM backend behind the same adapter interface, expand adversarial scenario coverage, and add CI enforcement of reliability thresholds so regressions are blocked automatically.

## What This Project Says About Me as an AI Engineer
This project reflects me as an AI engineer who prioritizes reliability over novelty: I design systems with explicit contracts, test harnesses, and guardrails so outputs are verifiable and trustworthy. I iterate by building deterministic baselines first, then layering AI behavior with measurable evaluation. It also shows that I treat AI critically—using it to accelerate development while validating suggestions through tests and correcting flawed recommendations with evidence-driven decisions.

## AI Collaboration Reflection
During development, I used AI as a coding copilot for implementation planning, test design, and debugging edge cases in the scheduler and reliability evaluator. I used it to propose test scenarios (tight budgets, overlapping preferred times, recurrence edge cases), then validated each suggestion by running tests and comparing behavior against project rules.

One helpful AI suggestion was to enforce a strict output contract for the AI scheduler adapter (scheduled, skipped, warnings, rationale) and reject malformed/partial outputs with explicit parse errors. This improved reliability because invalid outputs fail fast instead of silently propagating bad data into the evaluation pipeline.

One flawed AI suggestion was an early recommendation to prioritize consistency score as the main pass/fail gate. That would have allowed highly consistent but policy-violating outputs to pass. I corrected this by making rule compliance the primary gate (budget limits, task coverage, duplicate prevention, priority checks) and using consistency as a secondary stability metric.

Key limitations remain: the current adapter defaults to a deterministic baseline model rather than a hosted LLM, scenario coverage is still finite, and evaluation checks focus on structural/task-level correctness rather than deeper semantic quality. In future iterations, I would integrate a real LLM behind the same adapter interface, add adversarial and long-horizon scenarios, and enforce reliability thresholds in CI to block regressions automatically.