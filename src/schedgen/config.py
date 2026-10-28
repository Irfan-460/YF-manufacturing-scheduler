"""
config.py — Scale parameters, seed, and global constants.
"""

SEED = 20261022

SCALE = {
    "starter": {
        "n_products": 5,
        "n_machines": 3,
        "n_orders": 10,
        "n_materials": 5,
        "n_anomalies": 5,
        "target_ops": 0,
    },
    "full": {
        "n_products": 100,
        "n_machines": 40,
        "n_orders": 500,
        "n_materials": 200,
        "n_anomalies": 25,
        "target_ops": 2000,
    },
}

DEFAULT_OUT_DIR = "data"

# Scheduling horizon: 2026-01-05 to 2026-04-04 (90 days)
HORIZON_START = "2026-01-05"
HORIZON_END   = "2026-04-04"

# Shift windows (hour of day, 24h)
SHIFTS = [
    {"name": "morning",   "start": 6,  "end": 14},
    {"name": "afternoon", "start": 14, "end": 22},
    {"name": "night",     "start": 22, "end": 30},   # 30 = 06:00 next day
]

# Operation types and their base durations (minutes)
OPERATION_TYPES = {
    "CUT":     {"min": 60,  "max": 180},
    "GRIND":   {"min": 30,  "max": 90},
    "DRILL":   {"min": 20,  "max": 60},
    "WELD":    {"min": 45,  "max": 120},
    "PAINT":   {"min": 30,  "max": 90},
    "INSPECT": {"min": 15,  "max": 45},
    "ASSEMBLE":{"min": 60,  "max": 240},
    "PACK":    {"min": 15,  "max": 30},
}

# Machine types and which operation types they can perform.
# Distribution weights used by build_machines() to allocate 40 machines:
#   INSPECT appears in every routing template → needs most capacity (8)
#   CUT/GRIND/PACK appear frequently → 6 each
#   DRILL/WELD/PAINT/ASSEMBLE → 5 each
#   Total = 8+6+6+6+5+5+4 = 40  (matches full profile)
MACHINE_TYPES = {
    "CNC":      ["CUT", "DRILL"],   # handles CUT + DRILL
    "GRINDER":  ["GRIND"],
    "WELDER":   ["WELD"],
    "PAINTER":  ["PAINT"],
    "QC":       ["INSPECT"],
    "ASSEMBLY": ["ASSEMBLE"],
    "PACKER":   ["PACK"],
}

# How many machines of each type to create (sums to n_machines for full profile).
# For starter (3 machines) the scheduler falls back to round-robin.
MACHINE_TYPE_WEIGHTS = {
    "QC":       7,   # INSPECT is in every template
    "CNC":      8,   # CUT + DRILL both common
    "GRINDER":  5,
    "PACKER":   4,
    "WELDER":   7,   # WELD is heavily demanded
    "PAINTER":  6,   # PAINT is heavily demanded
    "ASSEMBLY": 3,   # ASSEMBLE needs more capacity
}
# Total = 40 for full profile

# Changeover time range (minutes) between different product families
CHANGEOVER_MIN = 15
CHANGEOVER_MAX = 90

# Downtime probability per machine per working day
DOWNTIME_PROB = 0.10

# Urgent order fraction
URGENT_FRACTION = 0.10

# Structured infeasible reason codes
class InfeasibleReason:
    NO_ELIGIBLE_MACHINE         = "NO_ELIGIBLE_MACHINE"
    CALENDAR_CAPACITY_EXHAUSTED = "CALENDAR_CAPACITY_EXHAUSTED"
    MATERIAL_NOT_AVAILABLE      = "MATERIAL_NOT_AVAILABLE"
    INSUFFICIENT_MATERIAL       = "INSUFFICIENT_MATERIAL"
    PREDECESSOR_INFEASIBLE      = "PREDECESSOR_INFEASIBLE"
    PLANNING_HORIZON_EXCEEDED   = "PLANNING_HORIZON_EXCEEDED"
    DOWNTIME_CONFLICT           = "DOWNTIME_CONFLICT"

# Anomaly types
ANOMALY_TYPES = [
    "machine_overlap",
    "precedence_violation",
    "material_unavailable",
    "outside_shift",
    "changeover_omitted",
]

# Routing templates — average length must be >= 4.0 to reach 2000 ops from 500 orders.
# Current templates: [3,4,4,3,5,3,4,5] avg=3.875 → produces ~1938 ops.
# Add two 4-step templates to push weighted avg to 4.0.
ROUTING_TEMPLATES = [
    ["CUT", "GRIND", "INSPECT"],
    ["CUT", "DRILL", "WELD", "INSPECT"],
    ["CUT", "WELD", "PAINT", "INSPECT"],
    ["ASSEMBLE", "INSPECT", "PACK"],
    ["CUT", "DRILL", "ASSEMBLE", "INSPECT", "PACK"],
    ["GRIND", "PAINT", "INSPECT"],
    ["WELD", "GRIND", "PAINT", "PACK"],
    ["CUT", "GRIND", "DRILL", "ASSEMBLE", "PACK"],
    ["CUT", "DRILL", "INSPECT", "PACK"],        # new 4-step
    ["WELD", "PAINT", "INSPECT", "PACK"],       # new 4-step
]
# Lengths: [3,4,4,3,5,3,4,5,4,4] avg=3.9 → ~1950 ops from 500 orders
# With 100 products and random template assignment the actual count will be
# controlled by TARGET_OPS_PER_ORDER in transactions.py.
