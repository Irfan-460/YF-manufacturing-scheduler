# Data Dictionary

## Product
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| product_id | string | yes | PROD-2026-NNNNNN | yes (PK) | format regex |
| sku | string | yes | SKU-{FAM}-NNNN | yes | non-empty |
| product_name | string | yes | any | no | non-empty |
| family | string | yes | METAL,PLASTIC,ELECTRONIC,COMPOSITE,RUBBER | no | enum |
| unit_of_measure | string | yes | EA,KG,L,M | no | enum |
| lead_time_days | int | yes | 2–14 | no | >0 |
| is_active | bool | yes | true/false | no | — |

## Routing
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| routing_id | string | yes | ROUTE-{sku}-NN | yes (PK) | format |
| product_id | string | yes | FK→Product | no | FK exists |
| sku | string | yes | — | no | matches product |
| description | string | no | any | no | — |
| is_active | bool | yes | true/false | no | — |

## RoutingStep
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| routing_id | string | yes | FK→Routing | no | FK exists |
| step_seq | int | yes | ≥1 | no (PK composite) | sequential |
| operation_type | string | yes | CUT,GRIND,DRILL,WELD,PAINT,INSPECT,ASSEMBLE,PACK | no | enum |
| duration_min | int | yes | 15–240 | no | >0 |
| is_optional | bool | yes | true/false | no | — |

## Machine
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| machine_id | string | yes | MACH-NNN | yes (PK) | format |
| machine_name | string | yes | any | no | non-empty |
| machine_type | string | yes | CNC,GRINDER,WELDER,PAINTER,QC,ASSEMBLY,PACKER | no | enum |
| location | string | no | CELL-NN | no | — |
| capacity_parallel | int | yes | 1 | no | ≥1 |
| shift_name | string | yes | morning,afternoon,night | no | enum |
| shift_start_h | int | yes | 0–23 | no | 0–23 |
| shift_end_h | int | yes | 0–23 | no | 0–23 |
| is_active | bool | yes | true/false | no | — |

## MachineCalendar
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| calendar_id | string | yes | CAL-2026-NNNNNN | yes (PK) | format |
| machine_id | string | yes | FK→Machine | no | FK exists |
| calendar_date | date | yes | YYYY-MM-DD | no | in horizon |
| shift_name | string | yes | morning,afternoon,night | no | enum |
| avail_start | datetime | yes | YYYY-MM-DD HH:MM | no | < avail_end |
| avail_end | datetime | yes | YYYY-MM-DD HH:MM | no | > avail_start |
| is_available | bool | yes | true/false | no | — |
| downtime_reason | string | no | MAINTENANCE,null | no | — |

## Material
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| material_id | string | yes | MAT-2026-NNNNNN | yes (PK) | format |
| material_name | string | yes | any | no | non-empty |
| category | string | yes | RAW,COMPONENT,CHEMICAL,PACKAGING | no | enum |
| unit_of_measure | string | yes | KG,EA,L,M | no | enum |
| lead_time_days | int | yes | 1–9 | no | >0 |
| is_active | bool | yes | true/false | no | — |

## InventoryLot
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| lot_id | string | yes | LOT-2026-NNNNNN | yes (PK) | format |
| material_id | string | yes | FK→Material | no | FK exists |
| quantity | float | yes | 100–5000 | no | >0 |
| unit_of_measure | string | yes | KG,EA,L,M | no | enum |
| availability_date | date | yes | YYYY-MM-DD | no | in horizon |
| expiry_date | date | yes | YYYY-MM-DD | no | > availability_date |
| status | string | yes | AVAILABLE | no | enum |

## ProductionOrder
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| order_id | string | yes | ORD-2026-NNNNNN | yes (PK) | format |
| product_id | string | yes | FK→Product | no | FK exists |
| order_date | date | yes | YYYY-MM-DD | no | in horizon |
| due_date | date | yes | YYYY-MM-DD | no | ≥ order_date |
| quantity | int | yes | 10–499 | no | >0 |
| priority | string | yes | LOW,NORMAL,HIGH,URGENT | no | enum |
| status | string | yes | PLANNED,RELEASED,IN_PROGRESS,COMPLETED,CANCELLED | no | enum |
| is_urgent | bool | yes | true/false | no | — |

## OperationSchedule
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| schedule_id | string | yes | SCH-2026-NNNNNN | yes (PK) | format |
| operation_id | string | yes | FK→Operation | no | FK exists |
| order_id | string | yes | FK→ProductionOrder | no | FK exists |
| machine_id | string | no | FK→Machine | no | FK exists if set |
| planned_start | datetime | no | YYYY-MM-DD HH:MM | no | < planned_end |
| planned_end | datetime | no | YYYY-MM-DD HH:MM | no | > planned_start |
| changeover_min | int | yes | 0–90 | no | ≥0 |
| status | string | yes | SCHEDULED,INFEASIBLE | no | enum |
| is_feasible | bool | yes | true/false | no | — |
| infeasible_reason | string | no | any | no | set if infeasible |

## ChangeoverMatrix
| Field | Type | Required | Allowed Values | Unique | Validation |
|---|---|---|---|---|---|
| changeover_id | string | yes | CO-2026-NNNNNN | yes (PK) | format |
| from_family | string | yes | product family | no | enum |
| to_family | string | yes | product family | no | enum |
| duration_min | int | yes | 5–90 | no | >0 |

---

## Relationships / Cardinality

| From | To | Cardinality | Notes |
|---|---|---|---|
| Product | Routing | 1:1 | one active routing per product |
| Routing | RoutingStep | 1:N | ordered by step_seq |
| Product | ProductionOrder | 1:N | — |
| ProductionOrder | Operation | 1:N | one per routing step |
| Operation | OperationSchedule | 1:1 | one schedule row per operation |
| Machine | MachineCalendar | 1:N | one row per day |
| Product ↔ Material | ProductMaterial | N:M | bridge table |
| OperationType ↔ Machine | OperationMachineEligibility | N:M | bridge table |
| ProductFamily ↔ ProductFamily | ChangeoverMatrix | N:M | self-referential |
