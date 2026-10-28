"""
tests/test_master.py — Master data generation tests.
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


def setup_function():
    ids.reset()


def test_products_count():
    products = build_products(10)
    assert len(products) == 10


def test_products_unique_ids():
    ids.reset()
    products = build_products(10)
    assert products["product_id"].nunique() == 10


def test_products_unique_skus():
    ids.reset()
    products = build_products(10)
    assert products["sku"].nunique() == 10


def test_routings_fk():
    ids.reset()
    products = build_products(5)
    routings, steps = build_routings(products)
    assert set(routings["product_id"]).issubset(set(products["product_id"]))


def test_routing_steps_have_seq():
    ids.reset()
    products = build_products(5)
    _, steps = build_routings(products)
    assert (steps["step_seq"] >= 1).all()


def test_machines_count():
    ids.reset()
    machines = build_machines(10)
    assert len(machines) == 10


def test_machines_unique_ids():
    ids.reset()
    machines = build_machines(10)
    assert machines["machine_id"].nunique() == 10


def test_machine_calendars_fk():
    ids.reset()
    machines = build_machines(5)
    cals = build_machine_calendars(machines)
    assert set(cals["machine_id"]).issubset(set(machines["machine_id"]))


def test_machine_calendars_no_sunday():
    ids.reset()
    import pandas as pd
    machines = build_machines(3)
    cals = build_machine_calendars(machines)
    cals["dow"] = pd.to_datetime(cals["calendar_date"]).dt.dayofweek
    assert (cals["dow"] != 6).all()


def test_materials_count():
    ids.reset()
    mats = build_materials(20)
    assert len(mats) == 20


def test_inventory_lots_fk():
    ids.reset()
    mats = build_materials(10)
    lots = build_inventory_lots(mats, 50)
    assert set(lots["material_id"]).issubset(set(mats["material_id"]))


def test_product_material_bridge_fk():
    ids.reset()
    products = build_products(5)
    mats = build_materials(10)
    bridge = build_product_material_bridge(products, mats)
    assert set(bridge["product_id"]).issubset(set(products["product_id"]))
    assert set(bridge["material_id"]).issubset(set(mats["material_id"]))


def test_changeover_matrix_families():
    ids.reset()
    products = build_products(10)
    co = build_changeover_matrix(products)
    assert len(co) > 0
    assert (co["duration_min"] > 0).all()


def test_eligibility_fk():
    ids.reset()
    products = build_products(5)
    _, steps = build_routings(products)
    machines = build_machines(10)
    elig = build_operation_machine_eligibility(steps, machines)
    assert set(elig["machine_id"]).issubset(set(machines["machine_id"]))
