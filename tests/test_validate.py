"""
tests/test_validate.py — Validation check tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
from datetime import datetime, timedelta
from schedgen import ids
from schedgen.validate import (
    check_machine_overlap, check_precedence,
    check_material_availability, check_shift_calendar, check_changeover,
)


def _dt(s): return datetime.strptime(s, "%Y-%m-%d %H:%M")
def _fmt(dt): return dt.strftime("%Y-%m-%d %H:%M")


def test_machine_overlap_detected():
    ids.reset()
    base = datetime(2026, 1, 5, 9, 0)
    scheds = pd.DataFrame([
        {"schedule_id": "SCH-A", "operation_id": "OP-A", "order_id": "O1",
         "machine_id": "MACH-001", "planned_start": _fmt(base),
         "planned_end": _fmt(base + timedelta(hours=2)), "is_feasible": True, "changeover_min": 0},
        {"schedule_id": "SCH-B", "operation_id": "OP-B", "order_id": "O2",
         "machine_id": "MACH-001", "planned_start": _fmt(base + timedelta(hours=1)),
         "planned_end": _fmt(base + timedelta(hours=3)), "is_feasible": True, "changeover_min": 0},
    ])
    result = check_machine_overlap(scheds)
    assert len(result) >= 1
    assert result.iloc[0]["check_name"] == "machine_overlap"


def test_no_overlap_when_sequential():
    ids.reset()
    base = datetime(2026, 1, 5, 9, 0)
    scheds = pd.DataFrame([
        {"schedule_id": "SCH-A", "operation_id": "OP-A", "order_id": "O1",
         "machine_id": "MACH-001", "planned_start": _fmt(base),
         "planned_end": _fmt(base + timedelta(hours=2)), "is_feasible": True, "changeover_min": 0},
        {"schedule_id": "SCH-B", "operation_id": "OP-B", "order_id": "O2",
         "machine_id": "MACH-001", "planned_start": _fmt(base + timedelta(hours=2)),
         "planned_end": _fmt(base + timedelta(hours=4)), "is_feasible": True, "changeover_min": 0},
    ])
    result = check_machine_overlap(scheds)
    assert len(result) == 0


def test_precedence_violation_detected():
    ids.reset()
    base = datetime(2026, 1, 5, 9, 0)
    ops = pd.DataFrame([
        {"operation_id": "OP-1", "step_seq": 1},
        {"operation_id": "OP-2", "step_seq": 2},
    ])
    scheds = pd.DataFrame([
        {"schedule_id": "SCH-1", "operation_id": "OP-1", "order_id": "O1",
         "machine_id": "M1", "planned_start": _fmt(base),
         "planned_end": _fmt(base + timedelta(hours=2)), "is_feasible": True, "changeover_min": 0},
        {"schedule_id": "SCH-2", "operation_id": "OP-2", "order_id": "O1",
         "machine_id": "M2", "planned_start": _fmt(base + timedelta(hours=1)),
         "planned_end": _fmt(base + timedelta(hours=3)), "is_feasible": True, "changeover_min": 0},
    ])
    result = check_precedence(scheds, ops)
    assert len(result) >= 1
    assert result.iloc[0]["check_name"] == "precedence_violation"


def test_outside_shift_detected():
    ids.reset()
    # Op at 03:00, shift is 06:00–14:00
    op_start = datetime(2026, 1, 5, 3, 0)
    op_end   = datetime(2026, 1, 5, 4, 0)
    shift_start = datetime(2026, 1, 5, 6, 0)
    shift_end   = datetime(2026, 1, 5, 14, 0)
    scheds = pd.DataFrame([{
        "schedule_id": "SCH-X", "operation_id": "OP-X", "order_id": "O1",
        "machine_id": "MACH-001",
        "planned_start": _fmt(op_start), "planned_end": _fmt(op_end),
        "is_feasible": True, "changeover_min": 0,
    }])
    cals = pd.DataFrame([{
        "calendar_id": "CAL-1", "machine_id": "MACH-001",
        "calendar_date": "2026-01-05", "shift_name": "morning",
        "avail_start": _fmt(shift_start), "avail_end": _fmt(shift_end),
        "is_available": True, "downtime_reason": None,
    }])
    result = check_shift_calendar(scheds, cals)
    assert len(result) >= 1
    assert result.iloc[0]["check_name"] == "outside_shift"


def test_material_unavailable_detected():
    ids.reset()
    op_start = datetime(2026, 1, 5, 9, 0)
    mat_avail = datetime(2026, 1, 5, 11, 0)
    scheds = pd.DataFrame([{
        "schedule_id": "SCH-M", "operation_id": "OP-M", "order_id": "O1",
        "machine_id": "MACH-001",
        "planned_start": _fmt(op_start), "planned_end": _fmt(op_start + timedelta(hours=1)),
        "is_feasible": True, "changeover_min": 0,
    }])
    ops = pd.DataFrame([{"operation_id": "OP-M"}])
    orders = pd.DataFrame([{"order_id": "O1", "product_id": "PROD-001"}])
    prod_mat = pd.DataFrame([{"product_id": "PROD-001", "material_id": "MAT-001", "is_critical": True}])
    lots = pd.DataFrame([{"material_id": "MAT-001", "availability_date": mat_avail.strftime("%Y-%m-%d %H:%M")}])
    result = check_material_availability(scheds, ops, orders, prod_mat, lots)
    assert len(result) >= 1
    assert result.iloc[0]["check_name"] == "material_unavailable"


def test_changeover_omitted_detected():
    ids.reset()
    base = datetime(2026, 1, 5, 9, 0)
    # Two ops on same machine, different families, no gap
    scheds = pd.DataFrame([
        {"schedule_id": "SCH-C1", "operation_id": "OP-C1", "order_id": "O1",
         "machine_id": "MACH-001", "planned_start": _fmt(base),
         "planned_end": _fmt(base + timedelta(hours=2)), "is_feasible": True, "changeover_min": 0},
        {"schedule_id": "SCH-C2", "operation_id": "OP-C2", "order_id": "O2",
         "machine_id": "MACH-001", "planned_start": _fmt(base + timedelta(hours=2)),
         "planned_end": _fmt(base + timedelta(hours=4)), "is_feasible": True, "changeover_min": 0},
    ])
    ops = pd.DataFrame([
        {"operation_id": "OP-C1"},
        {"operation_id": "OP-C2"},
    ])
    orders = pd.DataFrame([
        {"order_id": "O1", "product_id": "PROD-001"},
        {"order_id": "O2", "product_id": "PROD-002"},
    ])
    products = pd.DataFrame([
        {"product_id": "PROD-001", "family": "METAL"},
        {"product_id": "PROD-002", "family": "PLASTIC"},
    ])
    co = pd.DataFrame([{"from_family": "METAL", "to_family": "PLASTIC", "duration_min": 30}])
    result = check_changeover(scheds, ops, orders, products, co)
    assert len(result) >= 1
    assert result.iloc[0]["check_name"] == "changeover_omitted"
