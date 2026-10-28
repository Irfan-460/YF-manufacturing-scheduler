"""
ids.py — Deterministic ID factories.
"""

_counters: dict[str, int] = {}


def _next(prefix: str, width: int = 6) -> str:
    _counters[prefix] = _counters.get(prefix, 0) + 1
    return f"{prefix}{str(_counters[prefix]).zfill(width)}"


def reset():
    _counters.clear()


def product_id() -> str:
    return _next("PROD-2026-")


def routing_id(sku: str) -> str:
    _counters[f"ROUTE-{sku}"] = _counters.get(f"ROUTE-{sku}", 0) + 1
    return f"ROUTE-{sku}-{str(_counters[f'ROUTE-{sku}']).zfill(2)}"


def machine_id() -> str:
    return _next("MACH-", 3)


def material_id() -> str:
    return _next("MAT-2026-")


def lot_id() -> str:
    return _next("LOT-2026-")


def order_id() -> str:
    return _next("ORD-2026-")


def op_id(order: str) -> str:
    key = f"OP-{order}"
    _counters[key] = _counters.get(key, 0) + 1
    return f"OP-{order}-{str(_counters[key]).zfill(2)}"


def schedule_id() -> str:
    return _next("SCH-2026-")


def calendar_id() -> str:
    return _next("CAL-2026-")


def changeover_id() -> str:
    return _next("CO-2026-")


def anomaly_id() -> str:
    return _next("ANOM-", 3)


def event_id() -> str:
    return _next("EVT-2026-")
