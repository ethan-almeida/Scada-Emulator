CREATE TABLE IF NOT EXISTS raw_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    node_id TEXT NOT NULL,
    register INTEGER NOT NULL,
    value REAL NOT NULL,
    quality INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS clean_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    node_id TEXT NOT NULL,
    register INTEGER NOT NULL,
    value REAL NOT NULL,
    quality INTEGER DEFAULT 0,
    scrubbed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS metric_snaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    node_id TEXT NOT NULL,
    window_minutes INTEGER NOT NULL,
    performance_ratio REAL,
    capacity_factor REAL,
    availability REAL,
    anomaly_flags TEXT
);

CREATE INDEX IF NOT EXISTS raw_ts ON raw_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS raw_node ON raw_telemetry(node_id, register);
CREATE INDEX IF NOT EXISTS clean_ts ON clean_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS clean_node ON clean_telemetry(node_id, register);
CREATE INDEX IF NOT EXISTS kpi_ts ON metric_snaps(timestamp);