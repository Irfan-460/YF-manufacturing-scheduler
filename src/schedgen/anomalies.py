"""
anomalies.py — Inject labelled edge cases into a copy of the schedule.

Guarantees exactly n_each instances of each of the five anomaly types.
Raises RuntimeError if a type cannot be injected after MAX_RETRIES attempts.

Ground-truth columns:
  anomaly_id, issue_type, schedule_id_a, schedule_id_b, machine_id,
  expected_label, description, cascade_of

cascade_of: anomaly_id of the primary anomaly this row is a direct consequence
            of, or None if this is a primary anomaly.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from . import ids
from .config import SEED

RNG = np.random.default_rng(SEED + 99)
MAX_RETRIES = 200


def reset_rng():
    global RNG
    RNG = np.random.default_rng(SEED + 99)


def _parse(s) -> Optional[datetime]:
    if not s or (isinstance(s, float) and pd.isna(s)):
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            pass
    return None


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def inject_anomalies(
    schedules: pd.DataFrame,
    operations: pd.DataFrame,
    machine_calendars: pd.DataFrame,
    inventory_lots: pd.DataFrame,
    product_material: pd.DataFrame,
    products: pd.DataFrame,
    changeover_matrix: pd.DataFrame,
    orders: pd.DataFrame,
    n_each: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (modified_schedules, ground_truth_df).
    Injects exactly n_each instances of each anomaly type.
    Raises RuntimeError if any type cannot reach n_each after MAX_RETRIES.
    """
    sched = schedules.copy()
    gt_rows: list[dict] = []

    feasible = sched[sched["is_feasible"] == True].copy()
    if feasible.empty:
        raise RuntimeError("No feasible schedules to inject anomalies into")

    # Build order->product map for material_unavailable injection
    order_product = orders.set_index("order_id")["product_id"].to_dict()

    # ── 1. machine_overlap ──────────────────────────────────────────────────
    injected = 0
    attempts = 0
    while injected < n_each:
        attempts += 1
        if attempts > MAX_RETRIES:
            raise RuntimeError(f"machine_overlap: could only inject {injected}/{n_each}")
        by_machine = feasible.groupby("machine_id")
        candidates = [mid for mid, grp in by_machine if len(grp) >= 2]
        if not candidates:
            raise RuntimeError("machine_overlap: no machine has >=2 feasible ops")
        mid = RNG.choice(candidates)
        grp = feasible[feasible["machine_id"] == mid].sort_values("planned_start")
        # Pick two consecutive ops
        idx_a = grp.index[int(RNG.integers(0, len(grp) - 1))]
        idx_b = grp.index[grp.index.get_loc(idx_a) + 1]
        end_a = _parse(sched.at[idx_a, "planned_end"])
        if end_a is None:
            continue
        new_start = end_a - timedelta(minutes=30)
        new_end   = new_start + timedelta(minutes=60)
        anom_id = ids.anomaly_id()
        sched.at[idx_b, "planned_start"] = _fmt(new_start)
        sched.at[idx_b, "planned_end"]   = _fmt(new_end)
        gt_rows.append({
            "anomaly_id":     anom_id,
            "issue_type":     "machine_overlap",
            "schedule_id_a":  sched.at[idx_a, "schedule_id"],
            "schedule_id_b":  sched.at[idx_b, "schedule_id"],
            "machine_id":     mid,
            "expected_label": "VIOLATION",
            "description":    f"{sched.at[idx_b,'schedule_id']} overlaps {sched.at[idx_a,'schedule_id']} on {mid}",
            "cascade_of":     None,
        })
        injected += 1

    # ── 2. precedence_violation ─────────────────────────────────────────────
    injected = 0
    attempts = 0
    multi_op_orders = (
        operations.groupby("order_id")
        .filter(lambda g: len(g) >= 2)["order_id"]
        .unique()
        .tolist()
    )
    while injected < n_each:
        attempts += 1
        if attempts > MAX_RETRIES:
            raise RuntimeError(f"precedence_violation: could only inject {injected}/{n_each}")
        if not multi_op_orders:
            raise RuntimeError("precedence_violation: no orders with >=2 ops")
        oid = RNG.choice(multi_op_orders)
        ops_in_order = operations[operations["order_id"] == oid].sort_values("step_seq")
        op1 = ops_in_order.iloc[0]["operation_id"]
        op2 = ops_in_order.iloc[1]["operation_id"]
        sch1 = sched[sched["operation_id"] == op1]
        sch2 = sched[sched["operation_id"] == op2]
        if sch1.empty or sch2.empty:
            continue
        idx1, idx2 = sch1.index[0], sch2.index[0]
        if not sched.at[idx1, "is_feasible"] or not sched.at[idx2, "is_feasible"]:
            continue
        end1 = _parse(sched.at[idx1, "planned_end"])
        if end1 is None:
            continue
        new_start2 = end1 - timedelta(minutes=45)
        new_end2   = new_start2 + timedelta(minutes=int(ops_in_order.iloc[1]["duration_min"]))
        anom_id = ids.anomaly_id()
        sched.at[idx2, "planned_start"] = _fmt(new_start2)
        sched.at[idx2, "planned_end"]   = _fmt(new_end2)
        gt_rows.append({
            "anomaly_id":     anom_id,
            "issue_type":     "precedence_violation",
            "schedule_id_a":  sched.at[idx1, "schedule_id"],
            "schedule_id_b":  sched.at[idx2, "schedule_id"],
            "machine_id":     None,
            "expected_label": "VIOLATION",
            "description":    f"Step 2 ({op2}) starts before step 1 ({op1}) ends in order {oid}",
            "cascade_of":     None,
        })
        injected += 1

    # ── 3. material_unavailable ─────────────────────────────────────────────
    # Strategy: find a product that has a critical material with a late
    # availability date, then find a feasible schedule row whose order
    # references that product, and move its start to before the material date.
    if product_material.empty or inventory_lots.empty:
        raise RuntimeError("material_unavailable: no product_material or inventory_lots data")

    pm = product_material[product_material["is_critical"] == True].merge(
        inventory_lots[["material_id", "availability_date"]], on="material_id"
    )
    pm["avail_dt"] = pm["availability_date"].apply(_parse)
    # Keep only rows where avail_dt is at least 2h after horizon start
    from .config import HORIZON_START
    horizon_start_dt = datetime.strptime(HORIZON_START, "%Y-%m-%d")
    pm = pm[pm["avail_dt"] > horizon_start_dt + timedelta(hours=2)]

    injected = 0
    attempts = 0
    while injected < n_each:
        attempts += 1
        if attempts > MAX_RETRIES:
            raise RuntimeError(f"material_unavailable: could only inject {injected}/{n_each}")
        if pm.empty:
            raise RuntimeError("material_unavailable: no critical materials with late availability")
        row = pm.sample(1, random_state=int(RNG.integers(0, 99999))).iloc[0]
        pid      = row["product_id"]
        avail_dt = row["avail_dt"]
        # Find feasible schedule rows whose order belongs to this product
        prod_orders = [oid for oid, p in order_product.items() if p == pid]
        cands = sched[
            sched["is_feasible"] == True &
            sched["order_id"].isin(prod_orders) &
            sched["planned_start"].notna()
        ].copy()
        if cands.empty:
            # Fallback: any feasible row with planned_start after avail_dt
            cands = sched[sched["is_feasible"] == True].copy()
            cands = cands[cands["planned_start"].notna()]
            cands["ps_dt"] = cands["planned_start"].apply(_parse)
            cands = cands[cands["ps_dt"] > avail_dt]
        else:
            cands["ps_dt"] = cands["planned_start"].apply(_parse)
            cands = cands[cands["ps_dt"] > avail_dt]
        if cands.empty:
            continue
        idx = cands.sample(1, random_state=int(RNG.integers(0, 99999))).index[0]
        bad_start = avail_dt - timedelta(hours=2)
        bad_end   = bad_start + timedelta(minutes=60)
        anom_id = ids.anomaly_id()
        sched.at[idx, "planned_start"] = _fmt(bad_start)
        sched.at[idx, "planned_end"]   = _fmt(bad_end)
        gt_rows.append({
            "anomaly_id":     anom_id,
            "issue_type":     "material_unavailable",
            "schedule_id_a":  sched.at[idx, "schedule_id"],
            "schedule_id_b":  None,
            "machine_id":     sched.at[idx, "machine_id"],
            "expected_label": "VIOLATION",
            "description":    f"Op starts {bad_start} but material available {avail_dt} (product {pid})",
            "cascade_of":     None,
        })
        injected += 1

    # ── 4. outside_shift ────────────────────────────────────────────────────
    injected = 0
    attempts = 0
    while injected < n_each:
        attempts += 1
        if attempts > MAX_RETRIES:
            raise RuntimeError(f"outside_shift: could only inject {injected}/{n_each}")
        cands = sched[sched["is_feasible"] == True].copy()
        cands = cands[cands["machine_id"].notna() & cands["planned_start"].notna()]
        if cands.empty:
            raise RuntimeError("outside_shift: no feasible ops with machine_id")
        idx = cands.sample(1, random_state=int(RNG.integers(0, 99999))).index[0]
        mid = sched.at[idx, "machine_id"]
        ps  = _parse(sched.at[idx, "planned_start"])
        if ps is None:
            continue
        bad_start = ps.replace(hour=3, minute=0)
        bad_end   = bad_start + timedelta(minutes=60)
        anom_id = ids.anomaly_id()
        sched.at[idx, "planned_start"] = _fmt(bad_start)
        sched.at[idx, "planned_end"]   = _fmt(bad_end)
        gt_rows.append({
            "anomaly_id":     anom_id,
            "issue_type":     "outside_shift",
            "schedule_id_a":  sched.at[idx, "schedule_id"],
            "schedule_id_b":  None,
            "machine_id":     mid,
            "expected_label": "VIOLATION",
            "description":    f"Op moved to 03:00, outside any shift window on {mid}",
            "cascade_of":     None,
        })
        injected += 1

    # ── 5. changeover_omitted ───────────────────────────────────────────────
    prod_family = products.set_index("product_id")["family"].to_dict()
    co_map = {
        (r["from_family"], r["to_family"]): r["duration_min"]
        for _, r in changeover_matrix.iterrows()
    }

    injected = 0
    attempts = 0
    while injected < n_each:
        attempts += 1
        if attempts > MAX_RETRIES:
            raise RuntimeError(f"changeover_omitted: could only inject {injected}/{n_each}")
        by_machine = sched[sched["is_feasible"] == True].groupby("machine_id")
        candidates = [mid for mid, grp in by_machine if len(grp) >= 2]
        if not candidates:
            raise RuntimeError("changeover_omitted: no machine has >=2 feasible ops")
        mid = RNG.choice(candidates)
        grp = sched[(sched["machine_id"] == mid) & (sched["is_feasible"] == True)].sort_values("planned_start")
        # Find a consecutive pair from different families
        found = False
        for i in range(len(grp) - 1):
            idx_a = grp.index[i]
            idx_b = grp.index[i + 1]
            oid_a = sched.at[idx_a, "order_id"]
            oid_b = sched.at[idx_b, "order_id"]
            fam_a = prod_family.get(order_product.get(oid_a, ""), "")
            fam_b = prod_family.get(order_product.get(oid_b, ""), "")
            if fam_a == fam_b:
                continue
            required_co = co_map.get((fam_a, fam_b), 15)
            if required_co == 0:
                continue
            end_a = _parse(sched.at[idx_a, "planned_end"])
            if end_a is None:
                continue
            # Set op_b to start exactly when op_a ends (zero gap, no changeover)
            dur_b = int(sched.at[idx_b, "planned_end"] and
                        (_parse(sched.at[idx_b, "planned_end"]) - _parse(sched.at[idx_b, "planned_start"])).seconds // 60
                        if _parse(sched.at[idx_b, "planned_start"]) else 60) or 60
            anom_id = ids.anomaly_id()
            sched.at[idx_b, "planned_start"]  = _fmt(end_a)
            sched.at[idx_b, "planned_end"]    = _fmt(end_a + timedelta(minutes=dur_b))
            sched.at[idx_b, "changeover_min"] = 0
            gt_rows.append({
                "anomaly_id":     anom_id,
                "issue_type":     "changeover_omitted",
                "schedule_id_a":  sched.at[idx_a, "schedule_id"],
                "schedule_id_b":  sched.at[idx_b, "schedule_id"],
                "machine_id":     mid,
                "expected_label": "VIOLATION",
                "description":    (f"No changeover gap between {sched.at[idx_a,'schedule_id']} "
                                   f"and {sched.at[idx_b,'schedule_id']} on {mid} "
                                   f"({fam_a}->{fam_b}, required {required_co}min)"),
                "cascade_of":     None,
            })
            injected += 1
            found = True
            break
        # If no cross-family pair found on this machine, retry with another

    return sched, pd.DataFrame(gt_rows)
