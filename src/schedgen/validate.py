"""
validate.py — All schedule validation checks.

Every violation record contains:
  violation_id, check_name, severity, schedule_id, operation_id,
  machine_id, detail, detected_at
"""

from __future__ import annotations
import pandas as pd
from datetime import datetime
from typing import Optional

from .config import CHANGEOVER_MIN

DETECTED_AT = "2026-01-05 00:00:00"   # deterministic for reproducibility
_viol_counter = 0


def _viol_id() -> str:
    global _viol_counter
    _viol_counter += 1
    return f"VIO-{str(_viol_counter).zfill(6)}"


def reset_violation_counter():
    global _viol_counter
    _viol_counter = 0


def _parse(s) -> Optional[datetime]:
    if not s or pd.isna(s):
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            pass
    return None


def _row(check_name, severity, schedule_id, operation_id, machine_id, detail):
    return {
        "violation_id":  _viol_id(),
        "check_name":    check_name,
        "severity":      severity,
        "schedule_id":   schedule_id,
        "operation_id":  operation_id,
        "machine_id":    machine_id,
        "detail":        detail,
        "detected_at":   DETECTED_AT,
    }


def check_machine_overlap(schedules: pd.DataFrame) -> pd.DataFrame:
    """Flag pairs of ops on the same machine with overlapping time windows."""
    rows = []
    feasible = schedules[schedules["is_feasible"] == True].copy()
    feasible["ps"] = feasible["planned_start"].apply(_parse)
    feasible["pe"] = feasible["planned_end"].apply(_parse)

    for mid, grp in feasible.groupby("machine_id"):
        grp = grp.sort_values("ps").reset_index(drop=True)
        for i in range(len(grp) - 1):
            a = grp.iloc[i]
            b = grp.iloc[i + 1]
            if b["ps"] is not None and a["pe"] is not None and b["ps"] < a["pe"]:
                rows.append(_row(
                    "machine_overlap", "HIGH",
                    b["schedule_id"], b["operation_id"], mid,
                    f"{b['schedule_id']} starts {b['ps']} before {a['schedule_id']} ends {a['pe']}",
                ))
    return pd.DataFrame(rows)


def check_precedence(schedules: pd.DataFrame, operations: pd.DataFrame) -> pd.DataFrame:
    """Flag ops where step N starts before step N-1 ends."""
    rows = []
    merged = schedules.merge(
        operations[["operation_id", "step_seq"]], on="operation_id", how="inner"
    )
    merged["ps"] = merged["planned_start"].apply(_parse)
    merged["pe"] = merged["planned_end"].apply(_parse)

    for oid, grp in merged.groupby("order_id"):
        grp = grp.sort_values("step_seq").reset_index(drop=True)
        for i in range(1, len(grp)):
            prev = grp.iloc[i - 1]
            curr = grp.iloc[i]
            if prev["pe"] is None or curr["ps"] is None:
                continue
            if curr["ps"] < prev["pe"]:
                rows.append(_row(
                    "precedence_violation", "HIGH",
                    curr["schedule_id"], curr["operation_id"], curr["machine_id"],
                    (f"Step {curr['step_seq']} starts {curr['ps']} before "
                     f"step {prev['step_seq']} ends {prev['pe']} in order {oid}"),
                ))
    return pd.DataFrame(rows)


def check_material_availability(
    schedules: pd.DataFrame,
    operations: pd.DataFrame,
    orders: pd.DataFrame,
    product_material: pd.DataFrame,
    inventory_lots: pd.DataFrame,
) -> pd.DataFrame:
    """Flag ops that start before their product's critical material is available."""
    rows = []
    if product_material.empty or inventory_lots.empty:
        return pd.DataFrame(rows)

    pm = product_material.merge(
        inventory_lots[["material_id", "availability_date"]], on="material_id"
    )
    pm["avail_dt"] = pm["availability_date"].apply(_parse)
    critical = pm[pm["is_critical"] == True]
    if critical.empty:
        critical = pm
    mat_gate = critical.groupby("product_id")["avail_dt"].max().to_dict()

    order_product = orders.set_index("order_id")["product_id"].to_dict()
    active = schedules[schedules["planned_start"].notna()].copy()
    active["ps"] = active["planned_start"].apply(_parse)

    for _, row in active.iterrows():
        if row["ps"] is None:
            continue
        pid  = order_product.get(row["order_id"])
        gate = mat_gate.get(pid)
        if gate and row["ps"] < gate:
            rows.append(_row(
                "material_unavailable", "HIGH",
                row["schedule_id"], row["operation_id"], row["machine_id"],
                f"Op starts {row['ps']} but material available {gate} for product {pid}",
            ))
    return pd.DataFrame(rows)


def check_shift_calendar(
    schedules: pd.DataFrame, machine_calendars: pd.DataFrame
) -> pd.DataFrame:
    """Flag ops scheduled outside their machine's shift window."""
    rows = []
    cal = machine_calendars[machine_calendars["is_available"] == True].copy()
    if not cal.empty:
        cal["cs"] = cal["avail_start"].apply(_parse)
        cal["ce"] = cal["avail_end"].apply(_parse)

    feasible = schedules[schedules["is_feasible"] == True].copy()
    feasible["ps"] = feasible["planned_start"].apply(_parse)
    feasible["pe"] = feasible["planned_end"].apply(_parse)

    for _, row in feasible.iterrows():
        if row["ps"] is None or row["machine_id"] is None:
            continue
        mach_cal = cal[cal["machine_id"] == row["machine_id"]] if not cal.empty else cal
        covered = any(
            c["cs"] <= row["ps"] and row["pe"] <= c["ce"]
            for _, c in mach_cal.iterrows()
        )
        if not covered:
            rows.append(_row(
                "outside_shift", "HIGH",
                row["schedule_id"], row["operation_id"], row["machine_id"],
                f"Op [{row['ps']} - {row['pe']}] not within any shift window for {row['machine_id']}",
            ))
    return pd.DataFrame(rows)


def check_changeover(
    schedules: pd.DataFrame,
    operations: pd.DataFrame,
    orders: pd.DataFrame,
    products: pd.DataFrame,
    changeover_matrix: pd.DataFrame,
) -> pd.DataFrame:
    """Flag consecutive ops on same machine with different families and insufficient gap."""
    rows = []
    prod_family   = products.set_index("product_id")["family"].to_dict()
    order_product = orders.set_index("order_id")["product_id"].to_dict()
    co_map = {
        (r["from_family"], r["to_family"]): r["duration_min"]
        for _, r in changeover_matrix.iterrows()
    }

    merged = schedules[schedules["is_feasible"] == True].copy()
    merged["ps"] = merged["planned_start"].apply(_parse)
    merged["pe"] = merged["planned_end"].apply(_parse)
    merged["family"] = merged["order_id"].map(order_product).map(prod_family)

    for mid, grp in merged.groupby("machine_id"):
        grp = grp.sort_values("ps").reset_index(drop=True)
        for i in range(1, len(grp)):
            prev = grp.iloc[i - 1]
            curr = grp.iloc[i]
            if prev["family"] == curr["family"]:
                continue
            required_co = co_map.get((prev["family"], curr["family"]), CHANGEOVER_MIN)
            if prev["pe"] is None or curr["ps"] is None:
                continue
            gap_min = (curr["ps"] - prev["pe"]).total_seconds() / 60
            if gap_min < required_co:
                rows.append(_row(
                    "changeover_omitted", "HIGH",
                    curr["schedule_id"], curr["operation_id"], mid,
                    (f"Gap {gap_min:.0f}min < required {required_co}min "
                     f"changeover ({prev['family']}->{curr['family']})"),
                ))
    return pd.DataFrame(rows)


def run_all_checks(
    schedules: pd.DataFrame,
    operations: pd.DataFrame,
    orders: pd.DataFrame,
    products: pd.DataFrame,
    machine_calendars: pd.DataFrame,
    product_material: pd.DataFrame,
    inventory_lots: pd.DataFrame,
    changeover_matrix: pd.DataFrame,
) -> pd.DataFrame:
    reset_violation_counter()
    cols = ["violation_id", "check_name", "severity", "schedule_id",
            "operation_id", "machine_id", "detail", "detected_at"]
    empty = pd.DataFrame(columns=cols)
    checks = [
        check_machine_overlap(schedules),
        check_precedence(schedules, operations),
        check_material_availability(schedules, operations, orders, product_material, inventory_lots),
        check_shift_calendar(schedules, machine_calendars),
        check_changeover(schedules, operations, orders, products, changeover_matrix),
        empty,
    ]
    return pd.concat(checks, ignore_index=True)
