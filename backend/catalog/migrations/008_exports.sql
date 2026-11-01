BEGIN;
CREATE TABLE exports (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    target TEXT NOT NULL CHECK(target = 'website-standard-v1'),
    manifest_path TEXT NOT NULL UNIQUE,
    cost_report_path TEXT NOT NULL UNIQUE,
    privacy_policy_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('COMPLETE', 'FAILED')),
    error TEXT
);
CREATE TABLE export_items (
    export_id TEXT NOT NULL REFERENCES exports(id),
    photo_id TEXT NOT NULL REFERENCES photos(id),
    image_version_id TEXT NOT NULL REFERENCES image_versions(id),
    derivative_path TEXT NOT NULL UNIQUE,
    derivative_sha256 TEXT NOT NULL,
    thumbnail_path TEXT NOT NULL UNIQUE,
    thumbnail_sha256 TEXT NOT NULL,
    PRIMARY KEY(export_id, photo_id)
);
INSERT INTO schema_migrations(version, applied_at) VALUES (8, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
