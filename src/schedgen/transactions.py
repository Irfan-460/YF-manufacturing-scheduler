"""
transactions.py — Generate ProductionOrder and Operation records.

For the full profile (500 orders) the generator targets exactly 2,000 operations
by padding short-routing orders with an extra INSPECT step until the target is met.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from . import ids
from .config import (
    SEED, HORIZON_START, HORIZON_END, URGENT_FRACTION,
    OPERATION_TYPES, ROUTING_TEMPLATES,
)

RNG = np.random.default_rng(SEED + 1)


def reset_rng():
    global RNG
    RNG = np.random.default_rng(SEED + 1)


ORDER_STATUSES  = ["PLANNED", "RELEASED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
PRIORITY_LEVELS = ["LOW", "NORMAL", "HIGH", "URGENT"]


def build_orders(products: pd.DataFrame, n: int) -> pd.DataFrame:
    start_dt = datetime.strptime(HORIZON_START, "%Y-%m-%d")
    end_dt   = datetime.strptime(HORIZON_END,   "%Y-%m-%d")
    days     = (end_dt - start_dt).days
    prod_ids = products["product_id"].tolist()
    rows = []
    for _ in range(n):
        pid   = RNG.choice(prod_ids)
        order_date_offset = int(RNG.integers(0, days - 5))
        order_dt = start_dt + timedelta(days=order_date_offset)
        lead    = int(RNG.integers(3, 20))
        due_dt  = order_dt + timedelta(days=lead)
        is_urgent = RNG.random() < URGENT_FRACTION
        priority = "URGENT" if is_urgent else RNG.choice(
            ["LOW", "NORMAL", "HIGH"], p=[0.2, 0.5, 0.3]
        )
        rows.append({
            "order_id":    ids.order_id(),
            "product_id":  pid,
            "order_date":  order_dt.strftime("%Y-%m-%d"),
            "due_date":    due_dt.strftime("%Y-%m-%d"),
            "quantity":    int(RNG.integers(10, 500)),
            "priority":    priority,
            "status":      "PLANNED",
            "is_urgent":   is_urgent,
        })
    return pd.DataFrame(rows)


def build_operations(
    orders: pd.DataFrame,
    products: pd.DataFrame,
    routings: pd.DataFrame,
    routing_steps: pd.DataFrame,
    target_ops: int = 0,
) -> pd.DataFrame:
    """One Operation row per routing step per order.

    If target_ops > 0, pad orders (adding an extra INSPECT step) until
    len(operations) == target_ops.  This ensures the full profile always
    produces exactly 2,000 operations.
    """
    prod_to_routing = routings.set_index("product_id")["routing_id"].to_dict()
    rows = []
    for _, order in orders.iterrows():
        rid = prod_to_routing.get(order["product_id"])
        if rid is None:
            continue
        steps = routing_steps[routing_steps["routing_id"] == rid].sort_values("step_seq")
        for _, step in steps.iterrows():
            rows.append({
                "operation_id":   ids.op_id(order["order_id"]),
                "order_id":       order["order_id"],
                "routing_id":     rid,
                "step_seq":       step["step_seq"],
                "operation_type": step["operation_type"],
                "duration_min":   step["duration_min"],
                "status":         "PENDING",
            })

    # Pad to target_ops by appending extra INSPECT steps to existing orders
    if target_ops > 0 and len(rows) < target_ops:
        order_list = orders["order_id"].tolist()
        idx = 0
        while len(rows) < target_ops:
            oid = order_list[idx % len(order_list)]
            # Find current max step_seq for this order
            existing = [r for r in rows if r["order_id"] == oid]
            max_seq = max((r["step_seq"] for r in existing), default=0)
            dur = int(RNG.integers(
                OPERATION_TYPES["INSPECT"]["min"],
                OPERATION_TYPES["INSPECT"]["max"] + 1
            ))
            rows.append({
                "operation_id":   ids.op_id(oid),
                "order_id":       oid,
                "routing_id":     prod_to_routing.get(
                    orders.set_index("order_id").at[oid, "product_id"], ""
                ),
                "step_seq":       max_seq + 1,
                "operation_type": "INSPECT",
                "duration_min":   dur,
                "status":         "PENDING",
            })
            idx += 1

    return pd.DataFrame(rows)
