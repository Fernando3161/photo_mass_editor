BEGIN;

ALTER TABLE review_drafts ADD COLUMN approved_constraints TEXT NOT NULL DEFAULT '';
ALTER TABLE review_drafts ADD COLUMN semantic_change_consent INTEGER NOT NULL DEFAULT 0
    CHECK(semantic_change_consent IN (0, 1));

CREATE TABLE analysis_runs (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    source_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    template_version TEXT NOT NULL,
    config_signature TEXT NOT NULL,
    raw_response_json TEXT,
    sanitized_output_json TEXT,
    suggested_primary TEXT,
    suggested_tags_json TEXT NOT NULL DEFAULT '[]',
    suggested_edits TEXT,
    status TEXT NOT NULL CHECK(status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    estimated_cost REAL,
    actual_cost REAL,
    currency TEXT,
    usage_json TEXT,
    error TEXT,
    analyzed_at TEXT NOT NULL
);
CREATE INDEX analysis_runs_cache_idx
    ON analysis_runs(photo_id, source_hash, config_signature, status, analyzed_at);

ALTER TABLE review_drafts ADD COLUMN analysis_run_id TEXT REFERENCES analysis_runs(id);

CREATE TABLE compiled_prompts (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK(version_number > 0),
    parent_prompt_id TEXT REFERENCES compiled_prompts(id),
    source_hash TEXT NOT NULL,
    photo_revision INTEGER NOT NULL,
    draft_revision INTEGER NOT NULL,
    policy_version TEXT NOT NULL,
    compiler_version TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    compiled_text TEXT NOT NULL,
    user_modified INTEGER NOT NULL DEFAULT 0 CHECK(user_modified IN (0, 1)),
    approved_for_job INTEGER NOT NULL DEFAULT 0 CHECK(approved_for_job IN (0, 1)),
    generated_at TEXT NOT NULL,
    approved_at TEXT,
    UNIQUE(photo_id, version_number)
);
CREATE UNIQUE INDEX one_approved_prompt_per_photo
    ON compiled_prompts(photo_id) WHERE approved_for_job = 1;

INSERT INTO schema_migrations(version, applied_at)
VALUES (3, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
