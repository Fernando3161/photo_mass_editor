BEGIN;
ALTER TABLE review_drafts ADD COLUMN rule_suggestions_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE review_drafts ADD COLUMN rule_selected_ids_json TEXT;
ALTER TABLE review_drafts ADD COLUMN rule_instructions_override TEXT;
UPDATE review_drafts SET compiled_prompt_stale=1;
UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL WHERE approved_for_job=1;
INSERT INTO schema_migrations(version, applied_at) VALUES (15, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
