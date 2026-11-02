# V1.0.0 release notes

V1 is a local, single-user travel-photo catalog and review workstation. It preserves original files, records hashes and metadata, creates separate edit attempts, and exports only versions explicitly approved by the owner. The supported source formats are JPEG, PNG, TIFF, and WebP. The Windows launcher prepares the repository-local environment and serves the workstation on a trusted private LAN.

## Included

- Local catalog, thumbnails, metadata review, tags, subject, presets, and contact-sheet/filmstrip navigation.
- Optional pinned local CLIP recognition and private GPS-to-visited-city suggestions, with owner acceptance and undo.
- Versioned prompts, publication-sized derivatives, conservative local slider corrections, and an optional, explicitly authorized OpenAI image-edit adapter.
- Immutable attempts with pending/approved/rejected review, approved-only website export, privacy-filtered manifest, cost report, backup, and file audit.

## Known limits

- Local correction has five manual global controls and works on the 1600-pixel publication derivative. It has no auto-enhance, full-resolution corrected master, crop, straighten, white balance, or lens correction.
- Local corrections currently require an approved prompt. Generative batch work requires an approved prompt for each photo; the UI defaults to the generative engine.
- Local CLIP suggests coarse labels but does not write prose prompts. The paid analysis provider is unconfigured, and OpenAI image-edit responses provide usage rather than an invoice amount. The cost report distinguishes estimates from unknown actual charges.
- RAW and HEIC are unsupported. The one-command launcher is Windows-only and needs an active LAN gateway; Linux setup is manual. Private-LAN HTTP is unencrypted and is not a public hosting configuration.
- Successful software tests do not establish photographic fidelity or publication rights. Every exported image still needs owner visual and rights review.

The planned V2 work addresses local automation, batch workflow, prompt refinement, cost accounting, Content Credentials, and Linux startup in a separate plan. No paid API call or large image batch was part of release verification.
