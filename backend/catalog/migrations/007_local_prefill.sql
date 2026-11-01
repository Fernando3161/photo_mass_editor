BEGIN;
CREATE TABLE visited_cities (
    id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    private_lat REAL NOT NULL CHECK(private_lat BETWEEN -90 AND 90),
    private_lon REAL NOT NULL CHECK(private_lon BETWEEN -180 AND 180),
    radius_km REAL NOT NULL CHECK(radius_km > 0 AND radius_km <= 200),
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    UNIQUE(city, country)
);
CREATE TABLE catalog_suggestions (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    source_sha256 TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    proposed_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACCEPTED','DISMISSED','UNDONE')),
    applied_json TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    UNIQUE(photo_id, fingerprint)
);
CREATE INDEX catalog_suggestions_photo_idx ON catalog_suggestions(photo_id, created_at DESC);
CREATE TABLE catalog_location_batches (
    id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    applied_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    undone_at TEXT
);
INSERT INTO schema_migrations(version, applied_at) VALUES (7, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
