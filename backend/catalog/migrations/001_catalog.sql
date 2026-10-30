BEGIN;
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE photos (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    original_path TEXT NOT NULL UNIQUE,
    managed_original_path TEXT UNIQUE,
    thumbnail_path TEXT NOT NULL UNIQUE,
    thumbnail_sha256 TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    mime TEXT NOT NULL,
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    imported_at TEXT NOT NULL,
    capture_datetime_raw TEXT,
    capture_offset TEXT,
    camera TEXT,
    lens TEXT,
    orientation INTEGER,
    original_exif_json TEXT NOT NULL,
    private_lat REAL,
    private_lon REAL,
    source_missing INTEGER NOT NULL DEFAULT 0 CHECK(source_missing IN (0, 1)),
    duplicate_of_id TEXT REFERENCES photos(id),
    primary_subject_id TEXT REFERENCES subjects(id),
    editorial_description TEXT,
    city TEXT,
    country TEXT,
    revision INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX photos_sha256_idx ON photos(sha256);
CREATE INDEX photos_capture_idx ON photos(capture_datetime_raw);
CREATE TABLE subjects (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('CONTENT', 'CONDITION', 'OTHER'))
);
CREATE TABLE photo_tags (
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES tags(id),
    source TEXT NOT NULL CHECK(source IN ('AI', 'USER')),
    user_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(user_confirmed IN (0, 1)),
    confidence REAL CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1),
    PRIMARY KEY(photo_id, tag_id)
);
-- Review data is reserved for later phases, but migration integrity can be tested now.
CREATE TABLE image_versions (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id),
    version_number INTEGER NOT NULL CHECK(version_number > 0),
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    created_at TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(review_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    reviewed_at TEXT,
    rejection_reason TEXT,
    UNIQUE(photo_id, version_number)
);
CREATE UNIQUE INDEX one_approved_version_per_photo
    ON image_versions(photo_id) WHERE review_status = 'APPROVED';
CREATE TABLE review_events (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES image_versions(id),
    actor TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    next_status TEXT NOT NULL,
    note TEXT
);
INSERT INTO schema_migrations(version, applied_at) VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
