# PawPal+ Reliability Report

- Overall pass: **PASS**
- Aggregate compliance rate: **100.00%**
- Aggregate consistency rate: **100.00%**

## Scenario Results

### balanced_day
- Pass: PASS
- Compliance: 100.00%
- Consistency: 100.00%
- Scheduled: 3, Skipped: 0
- Checks:
  - all_tasks_present: PASS (All task_ids present.)
  - no_duplicate_tasks: PASS (No duplicate task_ids.)
  - budget_limit: PASS (Used=60, Budget=60)
  - priority_inversion: PASS (No comparison needed.)
  - field_consistency: PASS (All task fields valid.)

### tight_budget_priority_tradeoff
- Pass: PASS
- Compliance: 100.00%
- Consistency: 100.00%
- Scheduled: 2, Skipped: 1
- Checks:
  - all_tasks_present: PASS (All task_ids present.)
  - no_duplicate_tasks: PASS (No duplicate task_ids.)
  - budget_limit: PASS (Used=25, Budget=35)
  - priority_inversion: PASS (No priority inversion detected.)
  - field_consistency: PASS (All task fields valid.)

### overlap_detection_case
- Pass: PASS
- Compliance: 100.00%
- Consistency: 100.00%
- Scheduled: 3, Skipped: 0
- Checks:
  - all_tasks_present: PASS (All task_ids present.)
  - no_duplicate_tasks: PASS (No duplicate task_ids.)
  - budget_limit: PASS (Used=65, Budget=90)
  - priority_inversion: PASS (No comparison needed.)
  - field_consistency: PASS (All task fields valid.)
