# Validation Summary

## Checks Performed

| Check | Description | Hard/Soft |
|---|---|---|
| PK uniqueness | Every table's primary key is unique | Hard |
| FK integrity | All foreign keys reference existing parent rows | Hard |
| Enum values | All categorical fields use allowed values only | Hard |
| Date ordering | due_date ≥ order_date; avail_end > avail_start; expiry > availability | Hard |
| Machine overlap | No two ops on same machine have overlapping time windows | Hard |
| Precedence | Step N starts only after step N-1 ends | Hard |
| Material availability | Op start ≥ latest critical material availability date | Hard |
| Shift calendar | Op time window falls within machine's available shift | Hard |
| Changeover | Gap between consecutive ops on same machine ≥ required changeover | Hard |
| Arithmetic | Makespan, lateness, utilization derived from source records | Soft |
| Reproducibility | Two runs with same seed produce identical checksums | Hard |

## Anomaly Coverage

Five labelled anomaly types are injected into the `anomalous` dataset:

| Anomaly | Injected | Detected by check |
|---|---|---|
| machine_overlap | ✓ | check_machine_overlap |
| precedence_violation | ✓ | check_precedence |
| material_unavailable | ✓ | check_material_availability |
| outside_shift | ✓ | check_shift_calendar |
| changeover_omitted | ✓ | check_changeover |

Ground truth is stored separately in `ground_truth/ground_truth_{profile}.csv` and never merged into input features.

## Row Count Targets

| Table | Starter | Full |
|---|---|---|
| products | 5 | 100 |
| machines | 3 | 40 |
| orders | 10 | 500 |
| materials | 5 | 200 |
| operations | ~30 | ~2,000 |
| machine_calendars | ~780 | ~10,400 |
| inventory_lots | ~10 | ~400 |
