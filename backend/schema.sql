-- Fleet CIS Compliance Dashboard Schema

-- Teams (Synced from Fleet)
CREATE TABLE IF NOT EXISTS fleet_teams (
    team_id INTEGER PRIMARY KEY,
    team_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP
);

-- Hosts (Synced from Fleet)
CREATE TABLE IF NOT EXISTS fleet_hosts (
    host_id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    uuid TEXT,
    platform TEXT,
    platform_version TEXT,
    osquery_version TEXT,
    team_id INTEGER,
    team_name TEXT,
    online_status TEXT,
    last_seen TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES fleet_teams(team_id)
);

-- CIS Policies (Synced from Fleet)
CREATE TABLE IF NOT EXISTS cis_policies (
    policy_id INTEGER PRIMARY KEY,
    policy_name TEXT NOT NULL,
    cis_control TEXT,
    description TEXT,
    resolution TEXT,
    query TEXT,
    category TEXT,
    severity TEXT,
    platform TEXT
);

-- Policy Results (Time-series check results)
CREATE TABLE IF NOT EXISTS policy_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER,
    host_id INTEGER,
    status TEXT CHECK(status IN ('pass', 'fail', 'error')),
    checked_at TIMESTAMP,
    FOREIGN KEY (policy_id) REFERENCES cis_policies(policy_id),
    FOREIGN KEY (host_id) REFERENCES fleet_hosts(host_id)
);

-- Compliance Snapshots (Daily aggregates)
CREATE TABLE IF NOT EXISTS compliance_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL,
    team_id INTEGER,
    compliance_score REAL,
    critical_failures INTEGER,
    passing_hosts INTEGER,
    FOREIGN KEY (team_id) REFERENCES fleet_teams(team_id)
);

-- Labels (Synced from Fleet)
CREATE TABLE IF NOT EXISTS fleet_labels (
    label_id INTEGER PRIMARY KEY,
    label_name TEXT NOT NULL,
    label_type TEXT,
    description TEXT
);

-- Host Labels (Junction table for many-to-many)
CREATE TABLE IF NOT EXISTS host_labels (
    host_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL,
    PRIMARY KEY (host_id, label_id),
    FOREIGN KEY (host_id) REFERENCES fleet_hosts(host_id),
    FOREIGN KEY (label_id) REFERENCES fleet_labels(label_id)
);

-- Configuration Settings (User-customizable weights and thresholds)
CREATE TABLE IF NOT EXISTS config_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync Metadata (Tracks sync lifecycle for differential sync)
CREATE TABLE IF NOT EXISTS sync_metadata (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('running','success','failed')) DEFAULT 'running',
    hosts_changed INTEGER DEFAULT 0,
    policies_changed INTEGER DEFAULT 0,
    results_changed INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_hosts_team ON fleet_hosts(team_id);
CREATE INDEX IF NOT EXISTS idx_results_host ON policy_results(host_id);
CREATE INDEX IF NOT EXISTS idx_results_policy ON policy_results(policy_id);
CREATE INDEX IF NOT EXISTS idx_results_status ON policy_results(status);
CREATE INDEX IF NOT EXISTS idx_results_checked ON policy_results(checked_at);
CREATE INDEX IF NOT EXISTS idx_host_labels_host ON host_labels(host_id);
CREATE INDEX IF NOT EXISTS idx_host_labels_label ON host_labels(label_id);

-- Unique index for upsert support on policy_results
CREATE UNIQUE INDEX IF NOT EXISTS idx_results_policy_host
    ON policy_results(policy_id, host_id);

