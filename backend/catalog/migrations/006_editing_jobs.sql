BEGIN;

CREATE TABLE masks (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    publication_input_id TEXT NOT NULL REFERENCES publication_inputs(id),
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    created_at TEXT NOT NULL
);

CREATE TABLE edit_batches (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    engine TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'CANCELLED')),
    selection_json TEXT NOT NULL,
    authorized_at TEXT,
    budget_usd REAL
);

CREATE TABLE edit_jobs (
    id TEXT PRIMARY KEY,
    batch_id TEXT REFERENCES edit_batches(id),
    photo_id TEXT NOT NULL REFERENCES photos(id),
    compiled_prompt_id TEXT NOT NULL REFERENCES compiled_prompts(id),
    publication_input_id TEXT NOT NULL REFERENCES publication_inputs(id),
    publication_input_hash TEXT NOT NULL,
    engine TEXT NOT NULL CHECK(engine IN ('DETERMINISTIC', 'GENERATIVE')),
    model TEXT,
    settings_json TEXT NOT NULL,
    mask_id TEXT REFERENCES masks(id),
    signature TEXT NOT NULL,
    request_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
    error TEXT,
    raw_path TEXT UNIQUE,
    raw_sha256 TEXT,
    image_version_id TEXT UNIQUE REFERENCES image_versions(id),
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    usage_json TEXT,
    authorized_at TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
CREATE INDEX edit_jobs_photo_status_idx ON edit_jobs(photo_id, status, created_at);
CREATE INDEX edit_jobs_batch_idx ON edit_jobs(batch_id, status);

ALTER TABLE image_versions ADD COLUMN job_id TEXT REFERENCES edit_jobs(id);
ALTER TABLE image_versions ADD COLUMN publication_input_id TEXT REFERENCES publication_inputs(id);
ALTER TABLE image_versions ADD COLUMN mime TEXT;

INSERT INTO schema_migrations(version, applied_at)
VALUES (6, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
