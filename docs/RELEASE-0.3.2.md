# Lectic 0.3.2

This release introduces direct web article ingestion, streamlined sharing and preparation commands, and reduced onboarding friction.

Release date: September 28, 2026. [GitHub release](https://github.com/tyreamer/lectic/releases/tag/v0.3.2) · [PyPI package](https://pypi.org/project/lectic/0.3.2/) · [Website](https://tyreamer.github.io/lectic/).

## Changes

- **Direct Web Article Ingestion**: Pass any public web article or blog URL directly into `lectic start` or `lectic capture`. Extracts clean article text into structured Markdown using standard library HTTP and semantic HTML parsing without third-party scrapers or external dependencies. Walled gardens (Instagram, TikTok, X/Twitter, Facebook, Threads) remain saved as reference-only links.
- **Smart Sharing CLI**: `lectic share [NAME]` now automatically exports a standalone, portable HTML artifact when passed a collection name, while preserving `--tunnel` (or calling `lectic share` without arguments) for live assistant remote tunnels.
- **Direct Prepare Command**: `lectic prepare [NAME]` is now a first-class CLI command matching the developer mental model alongside `start` and `build`.
- **Streamlined CLI Help**: Organized CLI commands into distinct functional groups (`Core Workflow`, `Sharing & Access`, `Inspection & Maintenance`, `Packaged Artifacts`) for a cleaner developer experience.
- **URL Normalization**: URLs without explicit schemes (e.g., `example.com/article`) automatically normalize to HTTPS across CLI and capture workflows.
- **Capture Store Optimization**: When users supply explicit text alongside a URL, Lectic prioritizes the user's supplied text and avoids redundant network fetches.

## Compatibility

Python 3.10+ remains supported. Upgrade with:

```bash
python -m pip install --upgrade lectic
```

All 330 tests pass offline across Linux, macOS, and Windows.
