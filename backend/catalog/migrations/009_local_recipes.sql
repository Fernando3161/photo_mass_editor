BEGIN;
CREATE TABLE local_recipes (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id),
    version_number INTEGER NOT NULL CHECK(version_number > 0),
    source_hash TEXT NOT NULL,
    photo_revision INTEGER NOT NULL,
    publication_profile_id TEXT NOT NULL REFERENCES publication_profiles(id),
    profile_snapshot_json TEXT NOT NULL,
    preset_id TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    measurements_json TEXT NOT NULL,
    recommended_json TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    user_modified INTEGER NOT NULL CHECK(user_modified IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE(photo_id, version_number)
);
CREATE TABLE local_jobs (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id),
    recipe_id TEXT NOT NULL REFERENCES local_recipes(id),
    source_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    request_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    master_path TEXT UNIQUE,
    master_sha256 TEXT,
    master_width INTEGER,
    master_height INTEGER,
    image_version_id TEXT UNIQUE REFERENCES image_versions(id),
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
CREATE INDEX local_jobs_photo_status_idx ON local_jobs(photo_id,status,created_at);
ALTER TABLE image_versions ADD COLUMN local_job_id TEXT REFERENCES local_jobs(id);
INSERT INTO schema_migrations(version, applied_at) VALUES (9, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
