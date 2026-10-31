BEGIN;

-- Add owner-requested choices without changing existing, potentially customized presets.
INSERT INTO presets(id, version, name, structured_instructions, updated_at) VALUES
    ('museum-artwork', 1, 'Museum artwork', 'Draft preset: preserve the painting or sculpture exactly as photographed; correct exposure, white balance, glare, and perspective conservatively without inventing or altering artwork details.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('group-photo', 1, 'Group photo', 'Draft preset: keep every person recognizable with natural skin texture and proportions; balance exposure and color gently without adding, removing, or reshaping people.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('night-architecture', 1, 'Night architecture', 'Draft preset: retain the real nighttime atmosphere and building geometry; control highlights, shadows, color cast, and noise without inventing illumination or architectural details.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('food', 1, 'Food', 'Draft preset: keep the actual dish, ingredients, and colors recognizable; adjust exposure, white balance, and local contrast gently without adding or replacing food.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('panoramic-scene', 1, 'Panoramic scene', 'Draft preset: preserve the full scene, horizon, and wide composition; balance exposure and color across the frame without inventing scenery or changing the aspect ratio.', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

INSERT INTO schema_migrations(version, applied_at)
VALUES (5, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

COMMIT;
