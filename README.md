# Lectic

Save useful material once. Apply its methods to real work, with the source passages attached.

Lectic is an open-source **alpha** for people who want their AI assistant to reuse the talks, lessons and transcripts they trust. It keeps sources, extracted knowledge, reusable methods and previous results in a shared personal library. Your connected assistant supplies the reasoning.

## Start with one request

Paste this into **Codex or Claude Code**:

> Set up Lectic for me: https://github.com/tyreamer/lectic

The assistant follows [AGENTS.md](AGENTS.md), installs Lectic, configures available local assistants and checks the server. **Restart the assistant once** after setup.

Then say:

> Try Lectic with its offline debugging starter.

The bundled example produces a source-backed review of a sample debugging plan and a second checklist that reuses the same three procedures. It works without YouTube or a model API key. These are clearly labeled authored teaching examples, not live AI output or proof of effectiveness.

Then try your own work:

> Use my Debugging Starter to review this plan: [paste your plan]

For manual setup with Python 3.10 or newer:

```sh
python -m pip install --upgrade lectic
python -m lectic.cli setup --yes
```

After restarting your assistant, the offline trial is also available as `python -m lectic.cli try`. Run `python -m lectic.cli status` to see your knowledge folder, inbox, server health and configured connection checks. Setup cannot verify that an already-open assistant has reloaded its tools; restart is required.

## Save now, organize later

> Save this for later: [link]

> Add this transcript to Leadership.

> What could my saved Leadership material help me do?

> Use my Leadership collection to review this message.

A save without a collection goes straight to **Inbox**. Saving stores the exact link, text or file; it does not download a webpage, extract knowledge or start a paid model call. Personal notes stay separate from source evidence.

You can also drop notes, transcripts and web shortcuts into the **Lectic Inbox** folder reported by status. They appear when the assistant checks the library or inbox. Select items to sort; failed imports stay visible and the original file remains available for a safe retry.

## What works today

- **Source-backed work:** reviews, plans, checklists, lessons and other outcomes created by your assistant using cited knowledge.
- **Reuse and history:** saved collections work across projects sharing the same Lectic home. New goals can reuse existing knowledge. Updates preserve earlier source revisions and results.
- **Portable packs:** inspect, install and share a collection as a `.lectic` file. Installation verifies available source bytes and reports partial installs explicitly.
- **Honest evidence checks:** exact quotes, hashes and links are checked deterministically. This establishes traceability, not that a source is true or an interpretation is correct.
- **Public signature verification:** new signed packs use Ed25519. A valid signature establishes possession of the embedded key. Verify the publisher's fingerprint through a trusted channel to establish identity. Older HMAC packs are labeled unverified.
- **One personal home:** new installations use `~/.lectic`, or `LECTIC_HOME` if configured. Existing legacy project storage is preserved and identified in status.

The maintained website and starter catalog are at [tyreamer.github.io/lectic](https://tyreamer.github.io/lectic/). The catalog currently contains **one real bundled teaching pack**. There is no claim of a populated community marketplace.

## Input and connection limits

| Input or environment | Current behavior |
| --- | --- |
| Pasted text; local TXT, Markdown, VTT and SRT | Saved, then processed when useful for an authorized task |
| YouTube links | Saved immediately; optional `yt-dlp` retrieves available English captions during processing |
| Other web links | Saved as links; no general article downloader |
| PDF, images, video or audio files | Preserved as attachments; no built-in OCR or transcription |
| Codex and Claude Code on your machine | Setup configures a local server; restart once |
| Hosted chat or a phone | Needs a running HTTPS Lectic connector; a chat attachment alone does not install tools |

YouTube can block a network or have no accessible captions. Lectic reports this and keeps the capture; it never substitutes a video title for its content. See [YouTube support](docs/YOUTUBE.md).

For hosted chat, another computer or your phone, see the [cloud guide](docs/CLOUD.md). A share link works while its server is running; a quick tunnel changes address after restart. **Anyone holding the link can read and change your knowledge.** Keep it private. Connecting a local client to a remote server still runs retrieval on that remote server.

## Share and back up

```sh
python -m lectic.cli identity set "Alex Rivera" --contact alex@example.com
python -m lectic.cli pack "Leadership"
python -m lectic.cli install ./leadership.lectic --as Leadership --pin
python -m lectic.cli backup
```

Normal packs contain excerpts and source links. For material you may redistribute, `--include-sources` bundles full originals. `--team` also includes originals by default; `--exclude-sources` explicitly overrides it. Recipients need Lectic installed or connected. Unsupported or inaccessible sources can make a links-only install partial or impossible.

Version pinning records the installed version; nothing auto-updates packs. An explicit `update` request checks the origin and advances the version while preserving prior knowledge history. Backups and transfers merge additively and report collections that differ. Signing keys, cookies and connection secrets are not included in knowledge backups; preserve your signing identity separately in private storage.

Publishing by collection name rebuilds its current content. Full originals require `--include-sources`. Presigned uploads require a separate `--download-url`; a successful upload is only reported as published after that recipient link returns the correct bytes. Existing GitHub assets are preserved: use a new version or filename.

## Release and quality status

The source tree is preparing **0.3.1**. [Release notes](docs/RELEASE-0.3.1.md) distinguish candidate checks from publication. Installing from PyPI obtains the latest published package, which can differ from this branch.

The test suite covers storage, evidence linkage, workflows, transport, packs and regression cases. It does **not** establish that Lectic improves a user's work over a strong assistant with the same sources. The [evaluation protocol](docs/EVALUATION.md) and [review report](docs/reviews/2026-09-25-project-review.md) describe that remaining work.

For contributors: [development guide](docs/DEVELOPING.md), [architecture](DESIGN.md), [MCP tools](docs/MCP.md), [MIT license](LICENSE).
