"""
tests/test_transactions.py — Order and operation generation tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schedgen import ids
from schedgen.master import build_products, build_routings, build_machines
from schedgen.transactions import build_orders, build_operations


def setup_function():
    ids.reset()


def test_orders_count():
    ids.reset()
    products = build_products(5)
    orders = build_orders(products, 20)
    assert len(orders) == 20


def test_orders_fk():
    ids.reset()
    products = build_products(5)
    orders = build_orders(products, 20)
    assert set(orders["product_id"]).issubset(set(products["product_id"]))


def test_orders_due_after_order_date():
    ids.reset()
    import pandas as pd
    products = build_products(5)
    orders = build_orders(products, 20)
    orders["order_dt"] = pd.to_datetime(orders["order_date"])
    orders["due_dt"]   = pd.to_datetime(orders["due_date"])
    assert (orders["due_dt"] >= orders["order_dt"]).all()


def test_orders_priority_values():
    ids.reset()
    products = build_products(5)
    orders = build_orders(products, 50)
    valid = {"LOW", "NORMAL", "HIGH", "URGENT"}
    assert set(orders["priority"]).issubset(valid)


def test_operations_fk_order():
    ids.reset()
    products = build_products(5)
    routings, steps = build_routings(products)
    orders = build_orders(products, 10)
    ops = build_operations(orders, products, routings, steps)
    assert set(ops["order_id"]).issubset(set(orders["order_id"]))


def test_operations_step_seq_starts_at_1():
    ids.reset()
    products = build_products(5)
    routings, steps = build_routings(products)
    orders = build_orders(products, 10)
    ops = build_operations(orders, products, routings, steps)
    assert (ops["step_seq"] >= 1).all()


def test_operations_unique_ids():
    ids.reset()
    products = build_products(5)
    routings, steps = build_routings(products)
    orders = build_orders(products, 10)
    ops = build_operations(orders, products, routings, steps)
    assert ops["operation_id"].nunique() == len(ops)
