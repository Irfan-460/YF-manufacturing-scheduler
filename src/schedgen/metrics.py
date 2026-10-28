"""
metrics.py — Compute schedule quality metrics.
"""

from __future__ import annotations
import pandas as pd
from datetime import datetime
from typing import Optional


def _parse(s) -> Optional[datetime]:
    if not s or pd.isna(s):
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            pass
    return None


def compute_metrics(
    schedules: pd.DataFrame,
    orders: pd.DataFrame,
    machine_calendars: pd.DataFrame,
    violations: pd.DataFrame,
) -> dict:
    feasible = schedules[schedules["is_feasible"] == True].copy()
    feasible["ps"] = feasible["planned_start"].apply(_parse)
    feasible["pe"] = feasible["planned_end"].apply(_parse)

    # Makespan
    if feasible.empty or feasible["ps"].isna().all():
        makespan_h = 0.0
    else:
        global_start = feasible["ps"].dropna().min()
        global_end   = feasible["pe"].dropna().max()
        makespan_h   = (global_end - global_start).total_seconds() / 3600 if global_start and global_end else 0.0

    # Per-order completion = max planned_end of its feasible ops
    order_completion = (
        feasible.groupby("order_id")["pe"]
        .max()
        .reset_index()
        .rename(columns={"pe": "completion_dt"})
    )
    orders_m = orders.merge(order_completion, on="order_id", how="left")
    orders_m["due_dt"] = orders_m["due_date"].apply(_parse)
    # Lateness: only orders that have a completion_dt (>=1 feasible op).
    # Orders with no feasible ops have completion_dt=NaT -> lateness=0, not tardy.
    orders_m["lateness_h"] = orders_m.apply(
        lambda r: max(0.0, (r["completion_dt"] - r["due_dt"]).total_seconds() / 3600)
        if pd.notna(r.get("completion_dt")) and pd.notna(r.get("due_dt")) else 0.0,
        axis=1,
    )
    total_lateness_h  = float(orders_m["lateness_h"].sum())
    tardy_orders      = int((orders_m["lateness_h"] > 0).sum())
    # infeasible_orders: orders with at least one INFEASIBLE row
    infeasible_orders = int(
        schedules[schedules["is_feasible"] == False]["order_id"].nunique()
    )
    unscheduled_operations = int((schedules["is_feasible"] == False).sum())

    # Machine utilization
    util_rows = []
    cal = machine_calendars[machine_calendars["is_available"] == True].copy()
    if not cal.empty:
        cal["cs"] = cal["avail_start"].apply(_parse)
        cal["ce"] = cal["avail_end"].apply(_parse)
        cal["avail_h"] = [
            (r["ce"] - r["cs"]).total_seconds() / 3600 if r["cs"] and r["ce"] else 0
            for _, r in cal.iterrows()
        ]
        total_avail = cal.groupby("machine_id")["avail_h"].sum()
    else:
        total_avail = pd.Series(dtype=float)

    for mid, grp in feasible.groupby("machine_id"):
        busy_h = grp.apply(
            lambda r: (r["pe"] - r["ps"]).total_seconds() / 3600
            if r["ps"] and r["pe"] else 0, axis=1
        ).sum()
        avail_h = total_avail.get(mid, 0)
        util_rows.append({
            "machine_id":    mid,
            "busy_h":        round(busy_h, 2),
            "available_h":   round(avail_h, 2),
            "utilization_pct": round(100 * busy_h / avail_h, 2) if avail_h > 0 else 0.0,
        })
    machine_util = pd.DataFrame(util_rows)

    # Changeover total
    total_changeover_min = float(feasible["changeover_min"].sum()) if "changeover_min" in feasible.columns else 0.0

    # Violation counts
    viol_counts = violations["check_name"].value_counts().to_dict() if not violations.empty else {}

    return {
        "makespan_h":              round(makespan_h, 2),
        "total_lateness_h":        round(total_lateness_h, 2),
        "tardy_orders":            tardy_orders,
        "infeasible_orders":       infeasible_orders,
        "unscheduled_operations":  unscheduled_operations,
        "total_changeover_min":    round(total_changeover_min, 2),
        "total_violations":        len(violations),
        "violations_by_type":      viol_counts,
        "machine_utilization":     machine_util,
    }
