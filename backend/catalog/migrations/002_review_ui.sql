BEGIN;

ALTER TABLE photos ADD COLUMN review_state TEXT NOT NULL DEFAULT 'UNREVIEWED'
    CHECK(review_state IN ('UNREVIEWED', 'IN_PROGRESS', 'REVIEWED'));
ALTER TABLE photos ADD COLUMN metadata_reviewed_at TEXT;

CREATE TABLE presets (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
    name TEXT NOT NULL,
    structured_instructions TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO presets(id, version, name, structured_instructions, updated_at) VALUES
    ('natural-balance', 1, 'Natural balance', 'Draft preset: preserve the documentary look; adjust exposure, white balance, and tonal balance conservatively.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('architecture-clarity', 1, 'Architecture clarity', 'Draft preset: preserve structure; favor restrained perspective, contrast, and detail corrections.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('portrait-gentle', 1, 'Portrait gentle', 'Draft preset: preserve identity and natural texture; use restrained tonal and color corrections.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

CREATE TABLE review_drafts (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL UNIQUE REFERENCES photos(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
    preset_id TEXT REFERENCES presets(id),
    ai_allowance INTEGER NOT NULL DEFAULT 0 CHECK(ai_allowance BETWEEN 0 AND 10),
    ai_suggestion_editable TEXT NOT NULL DEFAULT '',
    user_instructions TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    compiled_prompt_stale INTEGER NOT NULL DEFAULT 1 CHECK(compiled_prompt_stale IN (0, 1))
);

CREATE INDEX photos_review_state_idx ON photos(review_state);
CREATE INDEX photo_tags_tag_idx ON photo_tags(tag_id, photo_id);

INSERT INTO schema_migrations(version, applied_at) VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
