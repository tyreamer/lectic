# Lectic 0.3.1 release candidate

This release makes the alpha's save → apply → reuse → update → share workflow easier to try and safer to trust. Publication is separate from preparation; this document does not claim that PyPI or the live website already serves this version.

## Changes

- Saving without a collection goes straight to Inbox. Sorting is optional. Selected drop items stay selected, failed imports retain the original, and retries reuse the capture rather than duplicating it.
- A bundled Debugging Starter produces an offline sample review and a second result from the same three cited procedures. `lectic try` and `lectic_starter` clearly identify the examples as prewritten teaching material.
- Pack updates persist changed interpretations even when source bytes are identical. Previous knowledge and build history remain available. Shared-home writers merge independent library additions and reject stale edits.
- New pack signatures use Ed25519, including publisher metadata. Recipients can verify the embedded key; trusting the claimed publisher requires a separate fingerprint check. Legacy HMAC packs are labeled unverified.
- Assistant reads, capture paths and knowledge exports reject Lectic credentials. Normal pack exports exclude full sources; explicit exclusion also overrides team inclusion.
- Setup checks real configured transports. It distinguishes a reachable server from the assistant restart needed to load tools. Invalid configuration is reported; an unreachable remote is not written over a working local setup.
- The catalog has one real, bundled, checksum-checked starter instead of unreachable examples. The maintained static website describes current behavior and supports mobile layouts.
- Publishing rebuilds current collection content, preserves existing GitHub assets, and verifies recipient download bytes. Presigned uploads require an explicit GET link.

## Compatibility

Python 3.10+ remains supported. Runtime dependencies now include `cryptography>=38` and `tomli>=2` on Python 3.10. Install or upgrade through the package so these dependencies are present. Source/knowledge schema versions are unchanged; the package, protocol server and pack metadata report release version 0.3.1 independently.

Existing homes and legacy project libraries are preserved. Signing keys and connector credentials are machine-local and excluded from knowledge backups; keep a separate private identity backup. Updating identity details preserves the signing key. A legacy HMAC identity can sign new Ed25519 packs using its existing random seed.

## Validation and limits

The [readiness audit](reviews/2026-09-25-release-readiness.md) records completed checks and remaining work. The [original review](reviews/2026-09-25-project-review.md) remains a historical baseline.

Synthetic examples and deterministic checks establish storage, workflow and evidence integrity. They do not prove improved task quality, retention, willingness to pay, or superiority over a capable assistant with the same sources. This remains an alpha; run the comparative user-study protocol before making those claims.
