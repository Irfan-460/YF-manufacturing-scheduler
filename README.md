# YottaFlex Scheduling System

End-to-end manufacturing job scheduling data generator, validator, and metrics engine.

## Quick Start

```bash
pip install -r requirements.txt

# Starter dataset (5 products, 3 machines, 10 orders)
python -m schedgen --profile starter --out data/starter

# Full dataset (100 products, 40 machines, 500 orders)
python -m schedgen --profile full --out data/full

# Full dataset with injected anomalies
python -m schedgen --profile full --out data/anomalous --anomalies

# Run tests
pytest tests/ -v

# Reproducibility check (two runs, compare checksums)
make repro
```

## Project Structure

```
yottaflex-scheduling/
├── src/schedgen/
│   ├── config.py        # seed, scale params, constants
│   ├── ids.py           # deterministic ID factories
│   ├── master.py        # Product, Machine, Material, Calendar, Changeover
│   ├── transactions.py  # ProductionOrder, Operation
│   ├── scheduler.py     # priority-dispatch feasible schedule builder
│   ├── anomalies.py     # labelled edge-case injection
│   ├── validate.py      # 5 hard-constraint checks
│   ├── metrics.py       # makespan, lateness, utilization
│   └── export.py        # CSV / JSON / SQL + manifest
├── tests/               # pytest suite
├── docs/                # schema.sql, data_dictionary.md, er_diagram.md
├── data/{starter,full,anomalous}/
└── ground_truth/        # ground_truth_{profile}.csv (kept separate)
```

## Fixed Seed

All generators use `SEED = 20261022`. Pass `--profile` and `--out` to parameterize scale.

## Outputs per Run

| File | Description |
|---|---|
| `products.csv` | 100 SKUs with family and lead time |
| `machines.csv` | 40 machines with type and shift |
| `machine_calendars.csv` | Daily availability with downtime |
| `materials.csv` | 200 raw/component materials |
| `inventory_lots.csv` | Batches with availability dates |
| `product_material.csv` | N:M bridge |
| `operation_machine_eligibility.csv` | N:M bridge |
| `changeover_matrix.csv` | Sequence-dependent changeover times |
| `orders.csv` | 500 production orders with priority |
| `operations.csv` | ~2,000 operations linked to orders |
| `schedules.csv` | Planned start/end per operation |
| `schedule_events.csv` | Immutable event history |
| `violations.csv` | Detected constraint violations |
| `metrics.json` | Makespan, lateness, utilization summary |
| `machine_utilization.csv` | Per-machine utilization % |
| `seed.sql` | SQL INSERT statements for all tables |
| `manifest.json` | Row counts + SHA-256 checksums |
| `ground_truth/ground_truth_{profile}.csv` | Known anomaly labels (separate) |

## Scheduling Algorithm

Priority-dispatch heuristic:
1. Sort orders: URGENT → HIGH → NORMAL → LOW, then by due_date ascending.
2. For each order, process operations in routing step_seq order.
3. For each operation, find the earliest eligible machine slot satisfying:
   - Machine shift calendar (no downtime)
   - Predecessor operation completed
   - Critical material available
   - Changeover gap from previous product family
4. If no slot found within horizon, mark INFEASIBLE with reason.

## Validation Checks

| Check | Rule |
|---|---|
| machine_overlap | No two ops on same machine overlap in time |
| precedence_violation | Step N starts only after step N-1 ends |
| material_unavailable | Op start ≥ critical material availability date |
| outside_shift | Op window falls within machine's shift calendar |
| changeover_omitted | Gap ≥ required changeover time between different families |

## Metrics

- **Makespan**: global_end − global_start (hours)
- **Total lateness**: Σ max(0, completion − due_date) (hours)
- **Tardy orders**: count of orders with lateness > 0
- **Machine utilization**: busy_h / available_h × 100%
- **Constraint violations**: count by type

## Reproducibility

```bash
make repro   # runs generator twice, compares SHA-256 checksums
```

Both runs must produce identical row counts and checksums for all CSV files.

## External Data

No external data used. All data is synthetic. Seed `20261022` ensures full reproducibility.
