BEGIN;
ALTER TABLE image_versions ADD COLUMN superseded_by_version_id TEXT REFERENCES image_versions(id);
ALTER TABLE image_versions ADD COLUMN superseded_at TEXT;
ALTER TABLE local_jobs ADD COLUMN replacement_of_version_id TEXT REFERENCES image_versions(id);
ALTER TABLE edit_jobs ADD COLUMN replacement_of_version_id TEXT REFERENCES image_versions(id);
CREATE INDEX image_versions_superseded_by_idx ON image_versions(superseded_by_version_id);
INSERT INTO schema_migrations(version, applied_at) VALUES (10, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
