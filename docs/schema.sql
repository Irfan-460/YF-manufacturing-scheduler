-- YottaFlex Scheduling Schema
-- Generated for PostgreSQL / SQLite compatible DDL

CREATE TABLE products (
    product_id      VARCHAR(20)  PRIMARY KEY,
    sku             VARCHAR(20)  NOT NULL UNIQUE,
    product_name    VARCHAR(100) NOT NULL,
    family          VARCHAR(20)  NOT NULL CHECK (family IN ('METAL','PLASTIC','ELECTRONIC','COMPOSITE','RUBBER')),
    unit_of_measure VARCHAR(5)   NOT NULL CHECK (unit_of_measure IN ('EA','KG','L','M')),
    lead_time_days  INTEGER      NOT NULL CHECK (lead_time_days > 0),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE routings (
    routing_id   VARCHAR(40) PRIMARY KEY,
    product_id   VARCHAR(20) NOT NULL REFERENCES products(product_id),
    sku          VARCHAR(20) NOT NULL,
    description  TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE routing_steps (
    routing_id      VARCHAR(40) NOT NULL REFERENCES routings(routing_id),
    step_seq        INTEGER     NOT NULL CHECK (step_seq >= 1),
    operation_type  VARCHAR(10) NOT NULL CHECK (operation_type IN ('CUT','GRIND','DRILL','WELD','PAINT','INSPECT','ASSEMBLE','PACK')),
    duration_min    INTEGER     NOT NULL CHECK (duration_min > 0),
    is_optional     BOOLEAN     NOT NULL DEFAULT FALSE,
    PRIMARY KEY (routing_id, step_seq)
);

CREATE TABLE machines (
    machine_id        VARCHAR(10)  PRIMARY KEY,
    machine_name      VARCHAR(50)  NOT NULL,
    machine_type      VARCHAR(20)  NOT NULL CHECK (machine_type IN ('CNC','GRINDER','WELDER','PAINTER','QC','ASSEMBLY','PACKER')),
    location          VARCHAR(20),
    capacity_parallel INTEGER      NOT NULL DEFAULT 1 CHECK (capacity_parallel >= 1),
    shift_name        VARCHAR(20)  NOT NULL CHECK (shift_name IN ('morning','afternoon','night')),
    shift_start_h     INTEGER      NOT NULL CHECK (shift_start_h BETWEEN 0 AND 23),
    shift_end_h       INTEGER      NOT NULL CHECK (shift_end_h BETWEEN 0 AND 23),
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE machine_calendars (
    calendar_id     VARCHAR(20)  PRIMARY KEY,
    machine_id      VARCHAR(10)  NOT NULL REFERENCES machines(machine_id),
    calendar_date   DATE         NOT NULL,
    shift_name      VARCHAR(20)  NOT NULL,
    avail_start     TIMESTAMP    NOT NULL,
    avail_end       TIMESTAMP    NOT NULL CHECK (avail_end > avail_start),
    is_available    BOOLEAN      NOT NULL DEFAULT TRUE,
    downtime_reason VARCHAR(50)
);

CREATE TABLE materials (
    material_id     VARCHAR(20)  PRIMARY KEY,
    material_name   VARCHAR(100) NOT NULL,
    category        VARCHAR(20)  NOT NULL CHECK (category IN ('RAW','COMPONENT','CHEMICAL','PACKAGING')),
    unit_of_measure VARCHAR(5)   NOT NULL CHECK (unit_of_measure IN ('KG','EA','L','M')),
    lead_time_days  INTEGER      NOT NULL CHECK (lead_time_days > 0),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE inventory_lots (
    lot_id            VARCHAR(20)  PRIMARY KEY,
    material_id       VARCHAR(20)  NOT NULL REFERENCES materials(material_id),
    quantity          NUMERIC(12,2) NOT NULL CHECK (quantity > 0),
    unit_of_measure   VARCHAR(5)   NOT NULL,
    availability_date DATE         NOT NULL,
    expiry_date       DATE         NOT NULL CHECK (expiry_date > availability_date),
    status            VARCHAR(20)  NOT NULL DEFAULT 'AVAILABLE'
);

CREATE TABLE product_material (
    product_id   VARCHAR(20)   NOT NULL REFERENCES products(product_id),
    material_id  VARCHAR(20)   NOT NULL REFERENCES materials(material_id),
    qty_per_unit NUMERIC(10,2) NOT NULL CHECK (qty_per_unit > 0),
    is_critical  BOOLEAN       NOT NULL DEFAULT FALSE,
    PRIMARY KEY (product_id, material_id)
);

CREATE TABLE operation_machine_eligibility (
    operation_type  VARCHAR(10) NOT NULL,
    machine_id      VARCHAR(10) NOT NULL REFERENCES machines(machine_id),
    efficiency_pct  INTEGER     NOT NULL CHECK (efficiency_pct BETWEEN 1 AND 100),
    PRIMARY KEY (operation_type, machine_id)
);

CREATE TABLE changeover_matrix (
    changeover_id VARCHAR(20) PRIMARY KEY,
    from_family   VARCHAR(20) NOT NULL,
    to_family     VARCHAR(20) NOT NULL,
    duration_min  INTEGER     NOT NULL CHECK (duration_min > 0)
);

CREATE TABLE orders (
    order_id    VARCHAR(20)  PRIMARY KEY,
    product_id  VARCHAR(20)  NOT NULL REFERENCES products(product_id),
    order_date  DATE         NOT NULL,
    due_date    DATE         NOT NULL CHECK (due_date >= order_date),
    quantity    INTEGER      NOT NULL CHECK (quantity > 0),
    priority    VARCHAR(10)  NOT NULL CHECK (priority IN ('LOW','NORMAL','HIGH','URGENT')),
    status      VARCHAR(20)  NOT NULL DEFAULT 'PLANNED',
    is_urgent   BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE operations (
    operation_id    VARCHAR(40)  PRIMARY KEY,
    order_id        VARCHAR(20)  NOT NULL REFERENCES orders(order_id),
    routing_id      VARCHAR(40)  NOT NULL REFERENCES routings(routing_id),
    step_seq        INTEGER      NOT NULL CHECK (step_seq >= 1),
    operation_type  VARCHAR(10)  NOT NULL,
    duration_min    INTEGER      NOT NULL CHECK (duration_min > 0),
    status          VARCHAR(20)  NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE schedules (
    schedule_id        VARCHAR(20)  PRIMARY KEY,
    operation_id       VARCHAR(40)  NOT NULL REFERENCES operations(operation_id),
    order_id           VARCHAR(20)  NOT NULL REFERENCES orders(order_id),
    machine_id         VARCHAR(10)  REFERENCES machines(machine_id),
    planned_start      TIMESTAMP,
    planned_end        TIMESTAMP    CHECK (planned_end > planned_start),
    changeover_min     INTEGER      NOT NULL DEFAULT 0 CHECK (changeover_min >= 0),
    status             VARCHAR(20)  NOT NULL,
    is_feasible        BOOLEAN      NOT NULL DEFAULT TRUE,
    infeasible_reason  TEXT
);

CREATE TABLE schedule_events (
    event_id     VARCHAR(20)  PRIMARY KEY,
    schedule_id  VARCHAR(20)  REFERENCES schedules(schedule_id),
    operation_id VARCHAR(40),
    event_type   VARCHAR(30)  NOT NULL,
    reason       TEXT,
    old_value    TEXT,
    new_value    TEXT,
    ts           TIMESTAMP    NOT NULL
);

CREATE TABLE violations (
    violation_id  VARCHAR(20)  PRIMARY KEY,
    check_name    VARCHAR(30)  NOT NULL CHECK (check_name IN ('machine_overlap','precedence_violation','material_unavailable','outside_shift','changeover_omitted')),
    severity      VARCHAR(10)  NOT NULL DEFAULT 'HIGH',
    schedule_id   VARCHAR(20)  REFERENCES schedules(schedule_id),
    operation_id  VARCHAR(40),
    machine_id    VARCHAR(10)  REFERENCES machines(machine_id),
    detail        TEXT,
    detected_at   TIMESTAMP    NOT NULL
);
