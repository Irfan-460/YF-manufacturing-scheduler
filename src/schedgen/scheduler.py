"""
scheduler.py — Feasible schedule builder.

Algorithm (priority-dispatching with least-loaded machine selection):
  1. Sort orders: URGENT first, then by due_date asc.
  2. For each order, process operations in step_seq order.
  3. For each operation, find the earliest valid slot across ALL eligible machines,
     selecting the machine whose current tail (machine_last_end) is earliest.
     For each machine the slot search advances past all busy intervals so no
     calendar window is skipped due to a mid-window conflict.
  4. Record OperationSchedule rows and machine timeline.
  5. If no slot found within horizon, mark INFEASIBLE with a structured reason code.
  6. If predecessor is infeasible, mark successor PREDECESSOR_INFEASIBLE immediately.

Infeasible reason codes (see config.InfeasibleReason):
  NO_ELIGIBLE_MACHINE        — no machine type can perform this operation
  CALENDAR_CAPACITY_EXHAUSTED — eligible machines exist but all slots exhausted
  MATERIAL_NOT_AVAILABLE     — critical material availability date not yet reached
  INSUFFICIENT_MATERIAL      — lot quantity < required quantity
  PREDECESSOR_INFEASIBLE     — a required predecessor step is infeasible
  PLANNING_HORIZON_EXCEEDED  — no slot found before horizon end
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from . import ids
from .config import SEED, HORIZON_END, InfeasibleReason

RNG = np.random.default_rng(SEED + 2)


def reset_rng():
    global RNG
    RNG = np.random.default_rng(SEED + 2)


PRIORITY_ORDER = {"URGENT": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
HORIZON_END_DT = datetime.strptime(HORIZON_END, "%Y-%m-%d") + timedelta(hours=23, minutes=59)


def _parse(dt_str: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def _earliest_slot(
    machine_id: str,
    cal_df: pd.DataFrame,
    busy: list[tuple[datetime, datetime]],
    not_before: datetime,
    duration_min: int,
) -> Optional[tuple[datetime, datetime]]:
    """Return the earliest (start, end) on this machine that:
      - falls within an available calendar window
      - does not overlap any already-busy interval
      - fits entirely before HORIZON_END_DT
    The search advances past every busy interval so no window is skipped.
    """
    mach_cal = cal_df[
        (cal_df["machine_id"] == machine_id) &
        (cal_df["is_available"] == True)
    ].copy()
    if mach_cal.empty:
        return None
    mach_cal["cs"] = mach_cal["avail_start"].apply(_parse)
    mach_cal["ce"] = mach_cal["avail_end"].apply(_parse)
    mach_cal = mach_cal[mach_cal["ce"] > not_before].sort_values("cs")

    # Sorted busy intervals for this machine
    busy_sorted = sorted(busy)

    for _, row in mach_cal.iterrows():
        win_start = row["cs"]
        win_end   = row["ce"]
        # Candidate start is the later of window open and not_before
        candidate = max(win_start, not_before)

        # Advance past any busy intervals that overlap candidate
        changed = True
        while changed:
            changed = False
            for bs, be in busy_sorted:
                if bs < candidate + timedelta(minutes=duration_min) and be > candidate:
                    # Overlap: push candidate to end of this busy block
                    candidate = be
                    changed = True
                    break

        slot_end = candidate + timedelta(minutes=duration_min)
        if slot_end <= win_end and slot_end <= HORIZON_END_DT:
            return candidate, slot_end

    return None


def build_schedule(
    orders: pd.DataFrame,
    operations: pd.DataFrame,
    products: pd.DataFrame,
    machines: pd.DataFrame,
    machine_calendars: pd.DataFrame,
    eligibility: pd.DataFrame,
    changeover_matrix: pd.DataFrame,
    product_material: pd.DataFrame,
    inventory_lots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (operation_schedules, schedule_events)."""

    prod_family   = products.set_index("product_id")["family"].to_dict()
    order_product = orders.set_index("order_id")["product_id"].to_dict()
    order_qty     = orders.set_index("order_id")["quantity"].to_dict()

    # eligible machines per operation_type
    elig_map: dict[str, list[str]] = {}
    for _, row in eligibility.iterrows():
        elig_map.setdefault(row["operation_type"], []).append(row["machine_id"])

    # changeover lookup: (from_family, to_family) -> duration_min
    co_map: dict[tuple[str, str], int] = {
        (r["from_family"], r["to_family"]): r["duration_min"]
        for _, r in changeover_matrix.iterrows()
    }

    # material gate per product
    mat_gate_dt:  dict[str, datetime] = {}
    mat_gate_qty: dict[str, bool]     = {}

    if not product_material.empty and not inventory_lots.empty:
        lot_agg = (
            inventory_lots.groupby("material_id")
            .agg(total_qty=("quantity", "sum"), availability_date=("availability_date", "max"))
            .reset_index()
        )
        pm = product_material.merge(lot_agg, on="material_id")
        pm["avail_dt"] = pm["availability_date"].apply(_parse)

        for pid, grp in pm.groupby("product_id"):
            critical = grp[grp["is_critical"] == True]
            src = critical if not critical.empty else grp
            mat_gate_dt[pid] = src["avail_dt"].max()
            max_order_qty = max(
                (order_qty.get(oid, 0) for oid, opid in order_product.items() if opid == pid),
                default=0,
            )
            for _, mat_row in src.iterrows():
                required = mat_row["qty_per_unit"] * max_order_qty
                mat_gate_qty[(pid, mat_row["material_id"])] = mat_row["total_qty"] >= required

    # machine state
    machine_last_end:    dict[str, datetime]      = {}
    machine_last_family: dict[str, Optional[str]] = {}
    machine_busy:        dict[str, list[tuple[datetime, datetime]]] = {
        mid: [] for mid in machines["machine_id"]
    }

    schedules: list[dict] = []
    events:    list[dict] = []

    def _log_event(sch_id, op_id, etype, reason):
        events.append({
            "event_id":     ids.event_id(),
            "schedule_id":  sch_id,
            "operation_id": op_id,
            "event_type":   etype,
            "reason":       reason,
            "old_value":    None,
            "new_value":    None,
            "ts":           "2026-01-05 00:00:00",
        })

    def _mark_infeasible(op_id, oid, reason_code, detail=""):
        sch_id = ids.schedule_id()
        schedules.append({
            "schedule_id":       sch_id,
            "operation_id":      op_id,
            "order_id":          oid,
            "machine_id":        None,
            "planned_start":     None,
            "planned_end":       None,
            "changeover_min":    0,
            "status":            "INFEASIBLE",
            "is_feasible":       False,
            "infeasible_reason": reason_code,
            "infeasible_detail": detail,
        })
        _log_event(sch_id, op_id, "INFEASIBLE", reason_code)
        return sch_id

    # Sort orders by priority then due_date
    sorted_orders = orders.copy()
    sorted_orders["_pri"] = sorted_orders["priority"].map(PRIORITY_ORDER).fillna(2)
    sorted_orders = sorted_orders.sort_values(["_pri", "due_date"]).reset_index(drop=True)

    # order_op_end: order_id -> {step_seq: (end_dt, is_feasible)}
    order_op_end: dict[str, dict[int, tuple[datetime, bool]]] = {}

    for _, order in sorted_orders.iterrows():
        oid = order["order_id"]
        pid = order["product_id"]
        fam = prod_family.get(pid, "UNKNOWN")
        ops = operations[operations["order_id"] == oid].sort_values("step_seq")
        order_op_end[oid] = {}

        for _, op in ops.iterrows():
            op_id   = op["operation_id"]
            op_type = op["operation_type"]
            dur     = int(op["duration_min"])
            seq     = int(op["step_seq"])

            # ── Predecessor check ────────────────────────────────────────────
            if seq > 1 and (seq - 1) in order_op_end[oid]:
                pred_end, pred_ok = order_op_end[oid][seq - 1]
                if not pred_ok:
                    _mark_infeasible(
                        op_id, oid,
                        InfeasibleReason.PREDECESSOR_INFEASIBLE,
                        f"Step {seq-1} is infeasible",
                    )
                    order_op_end[oid][seq] = (HORIZON_END_DT, False)
                    continue
                earliest = pred_end
            else:
                earliest = _parse(order["order_date"])

            # ── Material availability gate ───────────────────────────────────
            gate_dt = mat_gate_dt.get(pid)
            if gate_dt and gate_dt > earliest:
                earliest = gate_dt

            # ── Material quantity check ──────────────────────────────────────
            qty_ok = all(v for (p, _m), v in mat_gate_qty.items() if p == pid)
            if not qty_ok:
                _mark_infeasible(
                    op_id, oid,
                    InfeasibleReason.INSUFFICIENT_MATERIAL,
                    f"Insufficient lot quantity for product {pid}",
                )
                order_op_end[oid][seq] = (HORIZON_END_DT, False)
                continue

            # ── Machine eligibility ──────────────────────────────────────────
            eligible_machines = elig_map.get(op_type, [])
            if not eligible_machines:
                _mark_infeasible(
                    op_id, oid,
                    InfeasibleReason.NO_ELIGIBLE_MACHINE,
                    f"No machine type handles op_type={op_type}",
                )
                order_op_end[oid][seq] = (HORIZON_END_DT, False)
                continue

            # ── Find earliest valid slot across all eligible machines ─────────
            # Sort eligible machines by their current tail (least-loaded first)
            eligible_sorted = sorted(
                eligible_machines,
                key=lambda mid: machine_last_end.get(mid, earliest),
            )

            best_slot:   Optional[tuple[datetime, datetime]] = None
            best_machine: Optional[str] = None
            best_co_dur:  int = 0

            for mid in eligible_sorted:
                last_family = machine_last_family.get(mid)
                co_dur = 0
                if last_family and last_family != fam:
                    co_dur = co_map.get((last_family, fam), 30)

                not_before = max(earliest, machine_last_end.get(mid, earliest))
                if co_dur:
                    not_before = not_before + timedelta(minutes=co_dur)

                if not_before >= HORIZON_END_DT:
                    continue

                slot = _earliest_slot(
                    mid, machine_calendars, machine_busy[mid], not_before, dur
                )
                if slot is None:
                    continue

                # Keep the globally earliest slot across machines
                if best_slot is None or slot[0] < best_slot[0]:
                    best_slot    = slot
                    best_machine = mid
                    best_co_dur  = co_dur

            if best_slot is not None:
                slot_start, slot_end = best_slot
                mid = best_machine
                sch_id = ids.schedule_id()
                schedules.append({
                    "schedule_id":       sch_id,
                    "operation_id":      op_id,
                    "order_id":          oid,
                    "machine_id":        mid,
                    "planned_start":     slot_start.strftime("%Y-%m-%d %H:%M"),
                    "planned_end":       slot_end.strftime("%Y-%m-%d %H:%M"),
                    "changeover_min":    best_co_dur,
                    "status":            "SCHEDULED",
                    "is_feasible":       True,
                    "infeasible_reason": None,
                    "infeasible_detail": None,
                })
                _log_event(sch_id, op_id, "SCHEDULED",
                           f"Assigned to {mid} [{slot_start} - {slot_end}]")
                machine_busy[mid].append((slot_start, slot_end))
                machine_last_end[mid]    = slot_end
                machine_last_family[mid] = fam
                order_op_end[oid][seq]   = (slot_end, True)
            else:
                reason = (
                    InfeasibleReason.PLANNING_HORIZON_EXCEEDED
                    if all(
                        machine_last_end.get(mid, earliest) >= HORIZON_END_DT
                        for mid in eligible_machines
                    )
                    else InfeasibleReason.CALENDAR_CAPACITY_EXHAUSTED
                )
                _mark_infeasible(op_id, oid, reason,
                                 f"op_type={op_type}, {len(eligible_machines)} eligible machines")
                order_op_end[oid][seq] = (HORIZON_END_DT, False)

    return pd.DataFrame(schedules), pd.DataFrame(events)
