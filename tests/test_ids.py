"""
tests/test_ids.py — ID factory tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schedgen import ids


def test_product_ids_unique():
    ids.reset()
    generated = [ids.product_id() for _ in range(10)]
    assert len(set(generated)) == 10


def test_product_id_format():
    ids.reset()
    pid = ids.product_id()
    assert pid.startswith("PROD-2026-")
    assert len(pid.split("-")[-1]) == 6


def test_machine_id_format():
    ids.reset()
    mid = ids.machine_id()
    assert mid.startswith("MACH-")
    assert len(mid.split("-")[-1]) == 3


def test_order_id_format():
    ids.reset()
    oid = ids.order_id()
    assert oid.startswith("ORD-2026-")


def test_op_id_per_order():
    ids.reset()
    o1 = "ORD-2026-000001"
    o2 = "ORD-2026-000002"
    op1a = ids.op_id(o1)
    op1b = ids.op_id(o1)
    op2a = ids.op_id(o2)
    assert op1a == f"OP-{o1}-01"
    assert op1b == f"OP-{o1}-02"
    assert op2a == f"OP-{o2}-01"


def test_schedule_id_format():
    ids.reset()
    sid = ids.schedule_id()
    assert sid.startswith("SCH-2026-")


def test_routing_id_format():
    ids.reset()
    rid = ids.routing_id("SKU-MET-0001")
    assert rid == "ROUTE-SKU-MET-0001-01"


def test_reset_clears_counters():
    ids.reset()
    ids.product_id()
    ids.product_id()
    ids.reset()
    pid = ids.product_id()
    assert pid == "PROD-2026-000001"
