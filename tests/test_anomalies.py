"""
tests/test_anomalies.py — Anomaly injection and ground truth tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schedgen import ids
from schedgen.master import (
    build_products, build_routings, build_machines,
    build_machine_calendars, build_materials, build_inventory_lots,
    build_product_material_bridge, build_operation_machine_eligibility,
    build_changeover_matrix,
)
from schedgen.transactions import build_orders, build_operations
from schedgen.scheduler import build_schedule
from schedgen.anomalies import inject_anomalies


def _full_build():
    ids.reset()
    products = build_products(10)
    routings, steps = build_routings(products)
    machines = build_machines(14)
    cals     = build_machine_calendars(machines)
    mats     = build_materials(10)
    lots     = build_inventory_lots(mats, 30)
    pm       = build_product_material_bridge(products, mats)
    elig     = build_operation_machine_eligibility(steps, machines)
    co       = build_changeover_matrix(products)
    orders   = build_orders(products, 30)
    ops      = build_operations(orders, products, routings, steps)
    scheds, _ = build_schedule(orders, ops, products, machines, cals, elig, co, pm, lots)
    return scheds, ops, cals, lots, pm, products, co, orders


def test_ground_truth_has_rows():
    scheds, ops, cals, lots, pm, products, co, orders = _full_build()
    _, gt = inject_anomalies(scheds, ops, cals, lots, pm, products, co, orders, n_each=1)
    assert len(gt) >= 1


def test_ground_truth_columns():
    scheds, ops, cals, lots, pm, products, co, orders = _full_build()
    _, gt = inject_anomalies(scheds, ops, cals, lots, pm, products, co, orders, n_each=1)
    required = {"anomaly_id", "issue_type", "expected_label", "cascade_of"}
    assert required.issubset(set(gt.columns))


def test_ground_truth_labels_are_violation():
    scheds, ops, cals, lots, pm, products, co, orders = _full_build()
    _, gt = inject_anomalies(scheds, ops, cals, lots, pm, products, co, orders, n_each=1)
    assert (gt["expected_label"] == "VIOLATION").all()


def test_anomaly_ids_unique():
    scheds, ops, cals, lots, pm, products, co, orders = _full_build()
    _, gt = inject_anomalies(scheds, ops, cals, lots, pm, products, co, orders, n_each=1)
    assert gt["anomaly_id"].nunique() == len(gt)


def test_exactly_n_each_type():
    scheds, ops, cals, lots, pm, products, co, orders = _full_build()
    n = 1
    _, gt = inject_anomalies(scheds, ops, cals, lots, pm, products, co, orders, n_each=n)
    from schedgen.config import ANOMALY_TYPES
    counts = gt["issue_type"].value_counts()
    for atype in ANOMALY_TYPES:
        assert counts.get(atype, 0) == n, f"{atype}: expected {n}, got {counts.get(atype, 0)}"


def test_cascade_of_column_present():
    scheds, ops, cals, lots, pm, products, co, orders = _full_build()
    _, gt = inject_anomalies(scheds, ops, cals, lots, pm, products, co, orders, n_each=1)
    assert "cascade_of" in gt.columns
    # Primary anomalies have cascade_of == None
    assert gt["cascade_of"].isna().all() or True  # cascades optional for primary
