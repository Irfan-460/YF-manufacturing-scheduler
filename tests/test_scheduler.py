"""
tests/test_scheduler.py — Scheduler output tests.
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


def _build_all(n_prod=5, n_mach=7, n_ord=10, n_mat=5):
    ids.reset()
    products    = build_products(n_prod)
    routings, steps = build_routings(products)
    machines    = build_machines(n_mach)
    cals        = build_machine_calendars(machines)
    materials   = build_materials(n_mat)
    lots        = build_inventory_lots(materials, n_ord)
    prod_mat    = build_product_material_bridge(products, materials)
    elig        = build_operation_machine_eligibility(steps, machines)
    co          = build_changeover_matrix(products)
    orders      = build_orders(products, n_ord)
    ops         = build_operations(orders, products, routings, steps)
    return (orders, ops, products, machines, cals, elig, co, prod_mat, lots)


def test_schedule_returns_dataframes():
    args = _build_all()
    scheds, events = build_schedule(*args)
    import pandas as pd
    assert isinstance(scheds, pd.DataFrame)
    assert isinstance(events, pd.DataFrame)


def test_schedule_has_required_columns():
    args = _build_all()
    scheds, _ = build_schedule(*args)
    required = {"schedule_id", "operation_id", "order_id", "machine_id",
                "planned_start", "planned_end", "status", "is_feasible"}
    assert required.issubset(set(scheds.columns))


def test_schedule_ids_unique():
    args = _build_all()
    scheds, _ = build_schedule(*args)
    assert scheds["schedule_id"].nunique() == len(scheds)


def test_feasible_ops_have_times():
    args = _build_all()
    scheds, _ = build_schedule(*args)
    feasible = scheds[scheds["is_feasible"] == True]
    assert feasible["planned_start"].notna().all()
    assert feasible["planned_end"].notna().all()


def test_infeasible_ops_have_reason():
    args = _build_all()
    scheds, _ = build_schedule(*args)
    infeasible = scheds[scheds["is_feasible"] == False]
    if not infeasible.empty:
        assert infeasible["infeasible_reason"].notna().all()


def test_no_machine_overlap_in_baseline():
    """Baseline schedule (no anomaly injection) should have no machine overlaps."""
    from schedgen.validate import check_machine_overlap
    args = _build_all()
    scheds, _ = build_schedule(*args)
    overlaps = check_machine_overlap(scheds)
    assert len(overlaps) == 0, f"Unexpected overlaps: {overlaps}"
