BEGIN;

CREATE TABLE prompt_refinements (
    id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    base_prompt_id TEXT NOT NULL REFERENCES compiled_prompts(id),
    source_hash TEXT NOT NULL,
    publication_profile_id TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    template_version TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT,
    proposed_text TEXT,
    status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCEEDED','FAILED')),
    estimated_cost_usd REAL,
    usage_json TEXT,
    actual_cost_usd REAL,
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX prompt_refinements_photo_idx ON prompt_refinements(photo_id, created_at);
ALTER TABLE compiled_prompts ADD COLUMN refinement_id TEXT REFERENCES prompt_refinements(id);

INSERT INTO schema_migrations(version, applied_at) VALUES (12, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
