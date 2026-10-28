"""
__main__.py — CLI entry point.

Usage:
  python -m schedgen --profile starter --out data/starter
  python -m schedgen --profile full    --out data/full
  python -m schedgen --profile full    --out data/anomalous --anomalies
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from . import ids
from .config import SEED, SCALE, DEFAULT_OUT_DIR
from .master import (
    build_products, build_routings, build_machines,
    build_machine_calendars, build_materials, build_inventory_lots,
    build_product_material_bridge, build_operation_machine_eligibility,
    build_changeover_matrix, reset_rng as master_reset,
)
from .transactions import build_orders, build_operations, reset_rng as tx_reset
from .scheduler import build_schedule, reset_rng as sched_reset
from .anomalies import inject_anomalies, reset_rng as anom_reset
from .validate import run_all_checks
from .metrics import compute_metrics
from .export import export_all


def run(profile: str, out_dir: str, inject: bool = False):
    ids.reset()
    master_reset()
    tx_reset()
    sched_reset()
    anom_reset()
    cfg = SCALE[profile]

    print(f"[schedgen] profile={profile}  seed={SEED}  inject_anomalies={inject}")

    # ── Master data ──────────────────────────────────────────────────────────
    print("  Building master data …")
    products      = build_products(cfg["n_products"])
    routings, routing_steps = build_routings(products)
    machines      = build_machines(cfg["n_machines"])
    machine_cals  = build_machine_calendars(machines)
    materials     = build_materials(cfg["n_materials"])
    inv_lots      = build_inventory_lots(materials, cfg["n_orders"])
    prod_mat      = build_product_material_bridge(products, materials)
    eligibility   = build_operation_machine_eligibility(routing_steps, machines)
    changeover    = build_changeover_matrix(products)

    # ── Transactions ─────────────────────────────────────────────────────────
    print("  Building orders and operations …")
    orders     = build_orders(products, cfg["n_orders"])
    operations = build_operations(orders, products, routings, routing_steps, target_ops=cfg["target_ops"])

    # ── Schedule ─────────────────────────────────────────────────────────────
    print("  Running scheduler …")
    schedules, events = build_schedule(
        orders, operations, products, machines, machine_cals,
        eligibility, changeover, prod_mat, inv_lots,
    )

    # ── Anomaly injection ────────────────────────────────────────────────────
    ground_truth_df = __import__("pandas").DataFrame()
    if inject:
        print("  Injecting anomalies …")
        schedules, ground_truth_df = inject_anomalies(
            schedules, operations, machine_cals, inv_lots,
            prod_mat, products, changeover, orders,
            n_each=cfg["n_anomalies"] // 5,
        )

    # ── Validation ───────────────────────────────────────────────────────────
    print("  Running validation checks …")
    violations = run_all_checks(
        schedules, operations, orders, products,
        machine_cals, prod_mat, inv_lots, changeover,
    )

    # ── Metrics ──────────────────────────────────────────────────────────────
    metrics = compute_metrics(schedules, orders, machine_cals, violations)

    # ── Export ───────────────────────────────────────────────────────────────
    print(f"  Exporting to {out_dir} …")
    tables = {
        "products":          products,
        "routings":          routings,
        "routing_steps":     routing_steps,
        "machines":          machines,
        "machine_calendars": machine_cals,
        "materials":         materials,
        "inventory_lots":    inv_lots,
        "product_material":  prod_mat,
        "operation_machine_eligibility": eligibility,
        "changeover_matrix": changeover,
        "orders":            orders,
        "operations":        operations,
        "schedules":         schedules,
        "schedule_events":   events,
    }
    manifest = export_all(out_dir, tables, ground_truth_df, metrics, violations, SEED, profile)

    # ── Summary ──────────────────────────────────────────────────────────────
    total_ops       = len(operations)
    scheduled_ops   = int(schedules["is_feasible"].sum())
    unscheduled_ops = total_ops - scheduled_ops
    pct_sched       = 100.0 * scheduled_ops / total_ops if total_ops else 0.0

    print("\n  -- Summary --------------------------------------------------")
    print(f"    operations total : {total_ops}")
    print(f"    scheduled        : {scheduled_ops}  ({pct_sched:.1f}%)")
    print(f"    unscheduled      : {unscheduled_ops}  ({100-pct_sched:.1f}%)")
    print()
    print("    Unscheduled by reason code:")
    reason_counts = (
        schedules[~schedules["is_feasible"]]["infeasible_reason"]
        .value_counts()
    )
    if reason_counts.empty:
        print("      (none)")
    else:
        for reason, count in reason_counts.items():
            print(f"      {reason:<38s} {count:>5d}")
    print()
    for k, v in metrics.items():
        if k not in ("machine_utilization", "unscheduled_operations"):
            print(f"    {k}: {v}")
    print(f"    violations detected: {len(violations)}")
    print(f"    ground_truth rows:   {len(ground_truth_df)}")
    print(f"    manifest: {Path(out_dir) / 'manifest.json'}")
    print("  Done.\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="YottaFlex Schedule Data Generator")
    parser.add_argument("--profile", choices=["starter", "full"], default="starter")
    parser.add_argument("--out", default=None)
    parser.add_argument("--anomalies", action="store_true", help="Inject labelled anomalies")
    args = parser.parse_args()

    if args.out is None:
        suffix = "anomalous" if args.anomalies else args.profile
        args.out = f"{DEFAULT_OUT_DIR}/{suffix}"

    run(args.profile, args.out, inject=args.anomalies)


if __name__ == "__main__":
    main()
