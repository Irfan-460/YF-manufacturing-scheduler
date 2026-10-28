# Assumptions and Design Decisions

## Scheduling

1. **Single-machine capacity**: Each machine processes one operation at a time (capacity_parallel=1). Parallel capacity is modelled in schema but not exercised in the scheduler.
2. **Priority dispatch**: URGENT orders are scheduled first. Within the same priority, earlier due_date wins. This is a heuristic, not an optimal solver.
3. **Material gate**: Only *critical* materials (is_critical=True) block operation start. Non-critical materials are assumed available on day 0.
4. **Changeover**: Applied only when consecutive operations on the same machine belong to different product families. Same-family changeover uses a shorter random duration (5–19 min).
5. **Infeasibility and PREDECESSOR_INFEASIBLE**: If no eligible machine has a valid slot within the horizon, the operation is marked INFEASIBLE with a structured reason code. Any successor operation in the same order whose direct predecessor is infeasible is immediately marked INFEASIBLE with reason PREDECESSOR_INFEASIBLE (status BLOCKED in the schedule row). This prevents cascading attempts on an already-broken chain.
6. **Least-loaded machine selection**: For each operation the scheduler evaluates all eligible machines and picks the one whose current tail (machine_last_end) is earliest, then finds the earliest non-overlapping slot on that machine. This distributes load across machines rather than piling work onto the first machine in eligibility order.

## Metrics Definitions

7. **Makespan**: Wall-clock hours from the earliest `planned_start` to the latest `planned_end` among *feasible* (SCHEDULED) operations only. Infeasible operations do not contribute to makespan.
8. **Order completion time**: The maximum `planned_end` across all feasible operations belonging to an order. If an order has no feasible operations, its completion time is undefined (NULL) and it contributes 0 to lateness.
9. **Lateness**: `max(0, completion_dt - due_dt)` in hours, per order. Orders with no feasible operations have lateness = 0 (they are counted separately as infeasible_orders, not as tardy).
10. **Tardy orders**: Orders where lateness > 0. Orders with no feasible operations are NOT counted as tardy; they are counted as infeasible_orders.
11. **Infeasible orders**: Orders that have at least one INFEASIBLE schedule row (regardless of whether other ops in the order were scheduled).
12. **Machine utilization denominator**: Total available shift-hours from machine_calendars where is_available=True. Downtime windows are excluded from the denominator.

## Data Generation

6. **Routing templates**: Eight fixed templates cover common manufacturing sequences. Each product is assigned one template at random.
7. **Machine types**: Seven types map to operation types. A machine can only perform operations its type supports.
8. **Sundays excluded**: Machine calendars skip Sundays (weekday==6). Saturdays are included.
9. **Downtime**: 10% probability per machine per working day. Downtime reason is always "MAINTENANCE".
10. **Inventory lots**: 1–3 lots per material, availability spread over the first half of the horizon to create realistic material gates.

## Anomaly Injection

11. **Anomalies are additive**: Injected anomalies modify a copy of the schedule. The baseline (non-anomalous) schedule is always valid.
12. **Ground truth is separate**: `ground_truth_{profile}.csv` is never merged into input tables. It serves as the answer key only.
13. **n_each**: The number of instances per anomaly type is `n_anomalies // 5`. For the full profile this is 5 instances of each type (25 total).

## IDs

14. **Immutable IDs**: Once assigned, IDs are never reused or changed. Counters are reset only at the start of each `run()` call to ensure reproducibility.
15. **Zero-padded counters**: All numeric suffixes are zero-padded to fixed width (6 digits for most, 3 for MACH, ANOM).

## Scope Exclusions

16. **No optimizer**: The system uses a greedy heuristic. Optimal scheduling (e.g., MILP, CP-SAT) is out of scope.
17. **No real-time updates**: The scheduler is batch-only. Live rescheduling on machine failure is not implemented.
18. **No cost model**: Labour cost, energy cost, and tooling cost are not modelled.
