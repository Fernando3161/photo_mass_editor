BEGIN;
ALTER TABLE edit_jobs ADD COLUMN request_id TEXT;
ALTER TABLE edit_jobs ADD COLUMN calculated_cost_usd TEXT;
ALTER TABLE edit_jobs ADD COLUMN price_version TEXT;
ALTER TABLE prompt_refinements ADD COLUMN request_id TEXT;
ALTER TABLE prompt_refinements ADD COLUMN calculated_cost_usd TEXT;
ALTER TABLE prompt_refinements ADD COLUMN price_version TEXT;
ALTER TABLE analysis_runs ADD COLUMN request_id TEXT;
ALTER TABLE analysis_runs ADD COLUMN calculated_cost_usd TEXT;
ALTER TABLE analysis_runs ADD COLUMN price_version TEXT;
CREATE TABLE billing_reconciliations (
    id TEXT PRIMARY KEY,
    operation TEXT NOT NULL CHECK(operation IN ('editing','analysis','refinement')),
    receipt_id TEXT NOT NULL,
    provider_request_id TEXT,
    billed_usd TEXT NOT NULL,
    source_label TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE(operation, receipt_id)
);
INSERT INTO schema_migrations(version, applied_at) VALUES (13, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
