# Security policy

Photo Mass Editor is a single-user local application. The Windows and Linux launchers create a new Basic-auth password per run. They serve HTTP without encryption, so use LAN mode only on a trusted private network. Do not expose the port to the public internet or a tunnel. Other processes or users with access to the host may reach a loopback-only service; keep the machine itself protected.

Original photos, SQLite catalogs, precise GPS, model cache, attempts, exports, and real API credentials belong under ignored local paths. Treat data/ and config/openAI.env as private. The original-image viewer returns the original bytes, including embedded EXIF, to an authenticated browser. Approved website exports strip image metadata and limit manifest location to confirmed editorial city/country.

Please report a security issue privately to [fernandopenaherrera@gmail.com](mailto:fernandopenaherrera@gmail.com). Describe the affected revision, reproduction steps, and impact. Do not attach real photos, databases, coordinates, or provider keys. Rotate any credential you believe was exposed.

Pinned Python and Node packages and the hashed local model support reproducibility, but first installation still downloads from package registries and a model host. Keep dependencies updated and review their sources. Automated scans and past release checks cannot establish that a repository or running host is vulnerability-free.
