# Security policy

Photo Mass Editor is a single-user local application. The supported Windows launcher restricts LAN access with a new Basic-auth password per run. It serves HTTP without encryption, so use it only on a trusted private network. Do not expose the port to the public internet or a tunnel. A loopback-only manual server launch is suitable when LAN access is unnecessary.

Original photos, SQLite catalogs, precise GPS, model cache, attempts, exports, and real API credentials belong under ignored local paths. Treat data/ and config/openAI.env as private. The original-image viewer returns the original bytes, including embedded EXIF, to an authenticated browser. Approved website exports strip image metadata and limit manifest location to confirmed editorial city/country.

Please report a security issue privately to [fernandopenaherrera@gmail.com](mailto:fernandopenaherrera@gmail.com). Describe the affected revision, reproduction steps, and impact. Do not attach real photos, databases, coordinates, or provider keys. Rotate any credential you believe was exposed.

The [release audit](reports/RELEASE_AUDIT.md) records the latest review and residual risks. Automated scans cannot establish that a repository or running host is vulnerability-free.
