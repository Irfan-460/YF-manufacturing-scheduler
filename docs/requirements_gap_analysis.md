# Requirements Gap Analysis

Audited: 2026-01-05 | Baseline tests: 50 passed, 0 failed

## Gap Table

| # | Requirement | Existing Implementation | Gap / Defect | Required Change | Test | Status |
|---|---|---|---|---|---|---|
| G1 | Full profile must produce exactly 2,000 operations | Produces 1,895 (avg 3.79 steps/order) | Templates average 3.875 steps; random selection lands below 4.0 | Add one 4-step template so weighted average reaches 4.0; verify with test | `test_full_operation_count` | FIXED |
| G2 | 966/1895 operations infeasible due to machine capacity exhaustion | Infeasible reason is generic string "No eligible machine slot found for op_type=X" | Reason codes are free-text strings, not structured enums; requirement specifies MATERIAL_NOT_AVAILABLE, NO_ELIGIBLE_MACHINE, PREDECESSOR_INCOMPLETE, CALENDAR_CAPACITY_EXHAUSTED, PLANNING_HORIZON_EXCEEDED | Replace free-text with structured enum reason codes | `test_infeasible_reason_codes` | FIXED |
| G3 | Infeasible rate 51% (966/1895) — machine capacity exhausted | 40 machines cycling through 7 types gives only 5-6 machines per type; INSPECT/CUT/GRIND most demanded | Machine distribution is round-robin across 7 types; QC (INSPECT) gets only 5-6 machines but INSPECT appears in every routing template | Rebalance machine type distribution to match operation demand | `test_feasibility_rate` | FIXED |
| G4 | Predecessor-incomplete propagation | When step N is infeasible, step N+1 uses HORIZON_END_DT as placeholder and may still be attempted | Successor ops should be marked PREDECESSOR_INCOMPLETE, not attempted | Propagate infeasibility: if predecessor is infeasible, mark successor PREDECESSOR_INCOMPLETE without scheduling | `test_predecessor_incomplete_propagation` | FIXED |
| G5 | Violation records must have violation_id, severity, detection_timestamp | violations.csv has: check_name, schedule_id, operation_id, machine_id, detail | Missing: violation_id (PK), severity field, detected_at timestamp | Add violation_id, severity (HIGH for all hard constraints), detected_at to violation records | `test_violation_record_schema` | FIXED |
| G6 | Material quantity / inventory balance reconciliation | Scheduler gates on availability date only; qty_per_unit and lot quantity not checked | INSUFFICIENT_MATERIAL reason code never triggered; no quantity deduction | Add quantity check: compute required qty = order.quantity * product_material.qty_per_unit; check against available lot qty | `test_material_quantity_check` | FIXED |
| G7 | Exact full-profile operation count test | No test asserts operations == 2000 for full profile | Missing test | Add `test_full_operation_count` asserting len(ops) == 2000 | `test_full_operation_count` | FIXED |
| G8 | Lifecycle state transitions documented and tested | Operations have status="PENDING" only; schedules have SCHEDULED/INFEASIBLE | No test for valid/invalid lifecycle transitions; no RELEASED/IN_PROGRESS/COMPLETED states exercised | Add lifecycle transition validator and test | `test_lifecycle_transitions` | FIXED |
| G9 | Reproducibility script exits nonzero on mismatch | Makefile repro target uses inline Python | Works but not a standalone script; no dedicated repro.py | Add scripts/repro_check.py that exits 1 on mismatch | `test_reproducibility_starter` (existing) | FIXED |
| G10 | Ground truth must not be leaked into input features | ground_truth written to separate directory | Correct — ground_truth/ is separate from data/ | No change needed | Verified by directory structure | OK |
| G11 | Anomaly injection: material_unavailable links to actual product | Injection picks any feasible schedule and moves start before a material date | The injected schedule row's order_id may not belong to the product with the late material — the link is cosmetic | Tighten injection to pick a schedule whose order references a product with a late critical material | `test_anomaly_material_links_product` | FIXED |
| G12 | Metrics: unscheduled_operations count | metrics.json has infeasible_orders but not unscheduled_operations count | Missing metric | Add unscheduled_operations (infeasible schedule rows) to metrics output | `test_metrics_unscheduled` | FIXED |
| G13 | docs/schema.sql matches actual table columns | schema.sql has `operations` table but no `violation_id` in violations | violations table not in schema.sql at all | Add violations table DDL to schema.sql | Documentation | FIXED |
| G14 | README commands use `python -m src.schedgen` not `python -m schedgen` | README shows `python -m schedgen` | Wrong module path — package is under src/ | Fix README commands to use `python -m src.schedgen` | Manual verification | FIXED |
| G15 | Starter profile: n_anomalies=5, n_each = 5//5 = 1 per type | n_each = cfg["n_anomalies"] // 5 = 1 | Works but ground_truth for starter has 0 rows when inject=False | Correct — inject=False produces 0 ground truth rows by design | N/A | OK |

## Summary

- Gaps found: 13 requiring code changes, 2 already correct
- Critical gaps: G1 (wrong operation count), G3 (51% infeasibility), G4 (predecessor propagation), G6 (no quantity check)
- All gaps addressed in the implementation below
