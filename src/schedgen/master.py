"""
master.py — Generate parent/master tables:
  Product, Routing, RoutingStep, Machine, MachineCalendar,
  Material, InventoryLot, ChangeoverMatrix, ProductMaterial (bridge),
  OperationMachineEligibility (bridge).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from itertools import product as iterproduct

from . import ids
from .config import (
    SEED, HORIZON_START, HORIZON_END, SHIFTS,
    OPERATION_TYPES, MACHINE_TYPES, MACHINE_TYPE_WEIGHTS,
    CHANGEOVER_MIN, CHANGEOVER_MAX, DOWNTIME_PROB,
    ROUTING_TEMPLATES,
)

RNG = np.random.default_rng(SEED)


def reset_rng():
    global RNG
    RNG = np.random.default_rng(SEED)

PRODUCT_FAMILIES = ["METAL", "PLASTIC", "ELECTRONIC", "COMPOSITE", "RUBBER"]
MATERIAL_CATEGORIES = ["RAW", "COMPONENT", "CHEMICAL", "PACKAGING"]


def _horizon_days() -> int:
    s = datetime.strptime(HORIZON_START, "%Y-%m-%d")
    e = datetime.strptime(HORIZON_END,   "%Y-%m-%d")
    return (e - s).days


def build_products(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        pid = ids.product_id()
        family = PRODUCT_FAMILIES[i % len(PRODUCT_FAMILIES)]
        sku = f"SKU-{family[:3]}-{str(i+1).zfill(4)}"
        rows.append({
            "product_id":   pid,
            "sku":          sku,
            "product_name": f"{family.title()} Part {i+1:04d}",
            "family":       family,
            "unit_of_measure": "EA",
            "lead_time_days": int(RNG.integers(2, 15)),
            "is_active":    True,
        })
    return pd.DataFrame(rows)


def build_routings(products: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (routings, routing_steps)."""
    routings, steps = [], []
    for _, prod in products.iterrows():
        rid = ids.routing_id(prod["sku"])
        template = ROUTING_TEMPLATES[int(RNG.integers(0, len(ROUTING_TEMPLATES)))]
        routings.append({
            "routing_id":  rid,
            "product_id":  prod["product_id"],
            "sku":         prod["sku"],
            "description": f"Routing for {prod['sku']}",
            "is_active":   True,
        })
        for seq, op_type in enumerate(template, start=1):
            dur = int(RNG.integers(
                OPERATION_TYPES[op_type]["min"],
                OPERATION_TYPES[op_type]["max"] + 1
            ))
            steps.append({
                "routing_id":    rid,
                "step_seq":      seq,
                "operation_type": op_type,
                "duration_min":  dur,
                "is_optional":   False,
            })
    return pd.DataFrame(routings), pd.DataFrame(steps)


def build_machines(n: int) -> pd.DataFrame:
    """Build machines using weighted type distribution for full profile.
    For small n falls back to round-robin across all types."""
    rows = []
    machine_type_list = list(MACHINE_TYPES.keys())
    total_weight = sum(MACHINE_TYPE_WEIGHTS.values())

    # Build weighted sequence that sums to n
    if n >= total_weight:
        # Scale weights proportionally
        type_sequence = []
        for mtype, w in MACHINE_TYPE_WEIGHTS.items():
            count = round(w * n / total_weight)
            type_sequence.extend([mtype] * count)
        # Pad/trim to exactly n
        while len(type_sequence) < n:
            type_sequence.append(machine_type_list[len(type_sequence) % len(machine_type_list)])
        type_sequence = type_sequence[:n]
    else:
        # Small n: round-robin
        type_sequence = [machine_type_list[i % len(machine_type_list)] for i in range(n)]

    for i, mtype in enumerate(type_sequence):
        mid = ids.machine_id()
        shift = SHIFTS[i % len(SHIFTS)]
        rows.append({
            "machine_id":   mid,
            "machine_name": f"{mtype}-{str(i+1).zfill(3)}",
            "machine_type": mtype,
            "location":     f"CELL-{(i // 5) + 1:02d}",
            "capacity_parallel": 1,
            "shift_name":   shift["name"],
            "shift_start_h": shift["start"],
            "shift_end_h":   shift["end"] if shift["end"] <= 24 else shift["end"] - 24,
            "is_active":    True,
        })
    return pd.DataFrame(rows)


def build_machine_calendars(machines: pd.DataFrame) -> pd.DataFrame:
    """Daily availability records; inject downtime windows."""
    rows = []
    start_dt = datetime.strptime(HORIZON_START, "%Y-%m-%d")
    end_dt   = datetime.strptime(HORIZON_END,   "%Y-%m-%d")
    days = (end_dt - start_dt).days

    for _, mach in machines.iterrows():
        for d in range(days):
            day = start_dt + timedelta(days=d)
            # Skip Sundays (weekday==6)
            if day.weekday() == 6:
                continue
            is_down = RNG.random() < DOWNTIME_PROB
            sh = mach["shift_start_h"]
            eh = mach["shift_end_h"] if mach["shift_end_h"] > mach["shift_start_h"] else mach["shift_end_h"] + 24
            avail_start = day + timedelta(hours=int(mach["shift_start_h"]))
            avail_end   = day + timedelta(hours=int(eh))
            rows.append({
                "calendar_id":  ids.calendar_id(),
                "machine_id":   mach["machine_id"],
                "calendar_date": day.strftime("%Y-%m-%d"),
                "shift_name":   mach["shift_name"],
                "avail_start":  avail_start.strftime("%Y-%m-%d %H:%M"),
                "avail_end":    avail_end.strftime("%Y-%m-%d %H:%M"),
                "is_available": not is_down,
                "downtime_reason": "MAINTENANCE" if is_down else None,
            })
    return pd.DataFrame(rows)


def build_materials(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        mid = ids.material_id()
        cat = MATERIAL_CATEGORIES[i % len(MATERIAL_CATEGORIES)]
        rows.append({
            "material_id":   mid,
            "material_name": f"{cat.title()} Material {i+1:04d}",
            "category":      cat,
            "unit_of_measure": RNG.choice(["KG", "EA", "L", "M"]),
            "lead_time_days": int(RNG.integers(1, 10)),
            "is_active":     True,
        })
    return pd.DataFrame(rows)


def build_inventory_lots(materials: pd.DataFrame, n_orders: int) -> pd.DataFrame:
    """~2 lots per material on average, availability spread across horizon."""
    rows = []
    start_dt = datetime.strptime(HORIZON_START, "%Y-%m-%d")
    days = _horizon_days()
    for _, mat in materials.iterrows():
        n_lots = int(RNG.integers(2, 5))
        for _ in range(n_lots):
            avail_offset = int(RNG.integers(0, days // 2))
            avail_dt = start_dt + timedelta(days=avail_offset)
            qty = float(RNG.integers(1000, 10000))
            rows.append({
                "lot_id":        ids.lot_id(),
                "material_id":   mat["material_id"],
                "quantity":      qty,
                "unit_of_measure": mat["unit_of_measure"],
                "availability_date": avail_dt.strftime("%Y-%m-%d"),
                "expiry_date":   (avail_dt + timedelta(days=int(RNG.integers(30, 365)))).strftime("%Y-%m-%d"),
                "status":        "AVAILABLE",
            })
    return pd.DataFrame(rows)


def build_product_material_bridge(
    products: pd.DataFrame, materials: pd.DataFrame
) -> pd.DataFrame:
    """Each product requires 1–4 materials (N:M bridge)."""
    rows = []
    mat_ids = materials["material_id"].tolist()
    for _, prod in products.iterrows():
        n_mats = int(RNG.integers(1, 5))
        chosen = RNG.choice(mat_ids, size=min(n_mats, len(mat_ids)), replace=False)
        for mat_id in chosen:
            rows.append({
                "product_id":  prod["product_id"],
                "material_id": mat_id,
                "qty_per_unit": float(round(RNG.uniform(0.1, 10.0), 2)),
                "is_critical": bool(RNG.random() < 0.4),
            })
    return pd.DataFrame(rows)


def build_operation_machine_eligibility(
    routing_steps: pd.DataFrame, machines: pd.DataFrame
) -> pd.DataFrame:
    """Each operation type → eligible machines (N:M bridge)."""
    rows = []
    seen = set()
    for op_type in OPERATION_TYPES:
        eligible_types = [mt for mt, ops in MACHINE_TYPES.items() if op_type in ops]
        eligible_machines = machines[machines["machine_type"].isin(eligible_types)]
        for _, mach in eligible_machines.iterrows():
            key = (op_type, mach["machine_id"])
            if key not in seen:
                seen.add(key)
                rows.append({
                    "operation_type": op_type,
                    "machine_id":     mach["machine_id"],
                    "efficiency_pct": int(RNG.integers(80, 101)),
                })
    return pd.DataFrame(rows)


def build_changeover_matrix(products: pd.DataFrame) -> pd.DataFrame:
    """Sequence-dependent changeover times between product families."""
    rows = []
    families = products["family"].unique().tolist()
    for f_from, f_to in iterproduct(families, families):
        if f_from == f_to:
            duration = int(RNG.integers(5, 20))   # same family: short
        else:
            duration = int(RNG.integers(CHANGEOVER_MIN, CHANGEOVER_MAX + 1))
        rows.append({
            "changeover_id":   ids.changeover_id(),
            "from_family":     f_from,
            "to_family":       f_to,
            "duration_min":    duration,
        })
    return pd.DataFrame(rows)
