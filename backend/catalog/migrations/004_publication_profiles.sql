BEGIN;

CREATE TABLE publication_profiles (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL CHECK(version > 0),
    name TEXT NOT NULL,
    image_format TEXT NOT NULL CHECK(image_format IN ('JPEG', 'PNG')),
    file_extension TEXT NOT NULL,
    mime TEXT NOT NULL,
    max_long_edge INTEGER NOT NULL CHECK(max_long_edge > 0),
    quality INTEGER CHECK(quality IS NULL OR quality BETWEEN 1 AND 100),
    color_space TEXT NOT NULL,
    preserve_aspect_ratio INTEGER NOT NULL CHECK(preserve_aspect_ratio IN (0, 1)),
    allow_upscale INTEGER NOT NULL CHECK(allow_upscale IN (0, 1)),
    strip_metadata INTEGER NOT NULL CHECK(strip_metadata IN (0, 1)),
    active INTEGER NOT NULL CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE(name, version)
);

INSERT INTO publication_profiles(
    id, version, name, image_format, file_extension, mime, max_long_edge, quality,
    color_space, preserve_aspect_ratio, allow_upscale, strip_metadata, active, created_at
) VALUES (
    'website-standard-v1', 1, 'Website standard', 'JPEG', '.jpg', 'image/jpeg', 1600, 85,
    'sRGB', 1, 0, 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
);

ALTER TABLE review_drafts ADD COLUMN publication_profile_id TEXT REFERENCES publication_profiles(id);
UPDATE review_drafts SET publication_profile_id='website-standard-v1';

ALTER TABLE compiled_prompts ADD COLUMN publication_profile_id TEXT REFERENCES publication_profiles(id);
ALTER TABLE compiled_prompts ADD COLUMN publication_profile_snapshot_json TEXT;
UPDATE compiled_prompts
SET publication_profile_id='website-standard-v1',
    publication_profile_snapshot_json='{"id":"website-standard-v1","version":1,"name":"Website standard","image_format":"JPEG","file_extension":".jpg","mime":"image/jpeg","max_long_edge":1600,"quality":85,"color_space":"sRGB","preserve_aspect_ratio":true,"allow_upscale":false,"strip_metadata":true}'
WHERE publication_profile_id IS NULL;

-- Older prompts did not contain the publication-input rule in their compiled text.
-- Preserve their history, but require recompilation before any future edit job.
UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL;
UPDATE review_drafts SET compiled_prompt_stale=1;

CREATE TABLE publication_inputs (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    publication_profile_id TEXT NOT NULL REFERENCES publication_profiles(id),
    source_hash TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    image_format TEXT NOT NULL,
    mime TEXT NOT NULL,
    encoder_settings_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('READY', 'INVALID')),
    UNIQUE(photo_id, publication_profile_id, source_hash)
);
CREATE INDEX publication_inputs_photo_idx ON publication_inputs(photo_id, publication_profile_id);

INSERT INTO schema_migrations(version, applied_at)
VALUES (4, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
