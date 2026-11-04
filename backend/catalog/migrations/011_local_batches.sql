BEGIN;
CREATE TABLE named_local_recipes (
    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, settings_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE local_batches (
    id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE, input_signature TEXT NOT NULL,
    selection_json TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL
        CHECK (status IN ('QUEUED','RUNNING','COMPLETED','CANCELLED'))
);
ALTER TABLE local_jobs ADD COLUMN batch_id TEXT REFERENCES local_batches(id);
CREATE INDEX idx_local_jobs_batch ON local_jobs(batch_id);
INSERT INTO schema_migrations(version, applied_at) VALUES (11, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
