"""
tests/test_metrics.py — Metrics computation tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
from datetime import datetime, timedelta
from schedgen.metrics import compute_metrics


def _fmt(dt): return dt.strftime("%Y-%m-%d %H:%M")
def _fmtd(dt): return dt.strftime("%Y-%m-%d")


def test_makespan_computed():
    base = datetime(2026, 1, 5, 9, 0)
    scheds = pd.DataFrame([
        {"schedule_id": "S1", "operation_id": "O1", "order_id": "ORD1",
         "machine_id": "M1", "planned_start": _fmt(base),
         "planned_end": _fmt(base + timedelta(hours=2)),
         "is_feasible": True, "changeover_min": 0},
        {"schedule_id": "S2", "operation_id": "O2", "order_id": "ORD1",
         "machine_id": "M2", "planned_start": _fmt(base + timedelta(hours=2)),
         "planned_end": _fmt(base + timedelta(hours=5)),
         "is_feasible": True, "changeover_min": 0},
    ])
    orders = pd.DataFrame([{
        "order_id": "ORD1", "due_date": _fmtd(base + timedelta(days=1))
    }])
    cals = pd.DataFrame(columns=["machine_id", "avail_start", "avail_end", "is_available"])
    violations = pd.DataFrame(columns=["check_name"])
    m = compute_metrics(scheds, orders, cals, violations)
    assert m["makespan_h"] == 5.0


def test_tardy_orders():
    base = datetime(2026, 1, 5, 9, 0)
    scheds = pd.DataFrame([{
        "schedule_id": "S1", "operation_id": "O1", "order_id": "ORD1",
        "machine_id": "M1", "planned_start": _fmt(base),
        "planned_end": _fmt(base + timedelta(hours=10)),
        "is_feasible": True, "changeover_min": 0,
    }])
    # Due date is before completion
    orders = pd.DataFrame([{
        "order_id": "ORD1", "due_date": _fmtd(base)
    }])
    cals = pd.DataFrame(columns=["machine_id", "avail_start", "avail_end", "is_available"])
    violations = pd.DataFrame(columns=["check_name"])
    m = compute_metrics(scheds, orders, cals, violations)
    assert m["tardy_orders"] == 1
    assert m["total_lateness_h"] > 0


def test_violation_counts():
    scheds = pd.DataFrame(columns=["schedule_id", "operation_id", "order_id",
                                    "machine_id", "planned_start", "planned_end",
                                    "is_feasible", "changeover_min"])
    orders = pd.DataFrame(columns=["order_id", "due_date"])
    cals   = pd.DataFrame(columns=["machine_id", "avail_start", "avail_end", "is_available"])
    violations = pd.DataFrame([
        {"check_name": "machine_overlap"},
        {"check_name": "machine_overlap"},
        {"check_name": "precedence_violation"},
    ])
    m = compute_metrics(scheds, orders, cals, violations)
    assert m["total_violations"] == 3
    assert m["violations_by_type"]["machine_overlap"] == 2
