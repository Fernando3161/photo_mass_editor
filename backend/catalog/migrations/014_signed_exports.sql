BEGIN;
ALTER TABLE export_items ADD COLUMN signed_path TEXT;
ALTER TABLE export_items ADD COLUMN signed_sha256 TEXT;
ALTER TABLE export_items ADD COLUMN signer_identity TEXT;
ALTER TABLE export_items ADD COLUMN signer_cert_sha256 TEXT;
CREATE UNIQUE INDEX export_items_signed_path_unique ON export_items(signed_path) WHERE signed_path IS NOT NULL;
INSERT INTO schema_migrations(version, applied_at) VALUES (14, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
