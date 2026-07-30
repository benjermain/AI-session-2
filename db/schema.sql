DROP TABLE IF EXISTS safety_simulations;
DROP TABLE IF EXISTS synthesis_jobs;
DROP TABLE IF EXISTS genetic_payloads;
DROP TABLE IF EXISTS researchers;

CREATE TABLE researchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    bsl_clearance INTEGER NOT NULL CHECK (bsl_clearance BETWEEN 1 AND 4),
    department TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE genetic_payloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sequence TEXT NOT NULL,
    risk_tier INTEGER NOT NULL CHECK (risk_tier BETWEEN 1 AND 4),
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES researchers(id)
);

CREATE TABLE synthesis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER NOT NULL,
    payload_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    rejection_reason TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (researcher_id) REFERENCES researchers(id),
    FOREIGN KEY (payload_id) REFERENCES genetic_payloads(id)
);

CREATE TABLE safety_simulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload_id INTEGER NOT NULL,
    off_target_score REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'PASSED', 'WARNING', 'FAILED')),
    details TEXT,
    ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payload_id) REFERENCES genetic_payloads(id)
);
