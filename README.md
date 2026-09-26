<div align="center">

# Lectic

### Save what you trust. Your AI applies the method.

[![Tests](https://github.com/tyreamer/lectic/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/lectic/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lectic?color=38bdf8)](https://pypi.org/project/lectic/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399)](https://github.com/tyreamer/lectic/blob/main/LICENSE)
[![Signatures: Ed25519](https://img.shields.io/badge/signatures-Ed25519-a78bfa)](https://github.com/tyreamer/lectic/blob/main/docs/PACKS.md)
[![Catalog](https://img.shields.io/badge/starter-shelf-38bdf8)](https://tyreamer.github.io/lectic/registry.html)

**[Quickstart](#quickstart)** · **[How it Works](#the-solution)** · **[Daily Flow](#talk-naturally-to-your-assistant)** · **[Core Superpowers](#the-5-superpowers)** · **[Packs & Teams](#portable-packs--team-distribution)** · **[Status](#release--quality-status)**

Automatic setup for **Claude Code** and **OpenAI Codex**. Other compatible MCP clients need manual configuration; hosted chat needs a running HTTPS connector.

</div>

---

### The Problem

Useful source material can get scattered across separate chats and projects.

You watch a brilliant 40-minute engineering talk, find a definitive architecture decision record (ADR), or study a debugging postmortem. You paste it into Claude or ChatGPT, get an insightful answer, and close the tab.

**Tomorrow, you want to use that lesson again.** Finding the original passages and explaining how to apply them can mean repeating work.

### The Solution

**Lectic keeps the useful material together.** Save links, notes, and transcripts once. Your connected assistant extracts knowledge and applies reusable methods with source passages attached. Export a collection as a portable `.lectic` pack; configure a signing identity to add Ed25519 verification.

Save it once, then ask your connected assistant to apply the method to the next task. Lectic stores the knowledge; your assistant supplies the reasoning. General article links are saved as references, not downloaded automatically.

---

## Quickstart

### 1. Ask your assistant to set it up (Zero-command install)
Paste this into **Claude Code** or **OpenAI Codex**:

> Set up Lectic for me: https://github.com/tyreamer/lectic

It reads [AGENTS.md](AGENTS.md), installs the package, configures available local assistants, and checks the connection. **Restart your assistant once** after setup. Signing identity is an optional, separate step when you want to share signed packs.

### 2. Try the instant offline starter
Say to your assistant:

> Try Lectic with its offline debugging starter.

The bundled teaching pack saves a review of a sample debugging plan and a second checklist using the same three cited procedures. These are **prewritten examples from a fictional transcript**, not live AI output or proof of effectiveness. The trial itself runs offline without model API keys or source downloads; installation and your assistant may need a network connection.

Then try your own work:
> Use my Debugging Starter to review this plan: [paste your plan]

### 3. Or install via terminal

```bash
python -m pip install --upgrade lectic
python -m lectic.cli setup --yes
python -m lectic.cli try
```

Use Python 3.10 or newer. Run `python -m lectic.cli status` anytime to see your knowledge folder, inbox, and connection health. The module form works even when the `lectic` command is not on PATH.

---

## Talk Naturally to Your Assistant

Open any connected assistant and speak in plain English:

- **Save without friction:**
  > Save this for later: https://www.youtube.com/watch?v=…
  
  *(Goes straight to **Inbox**. Saving does not download the page, extract knowledge, or start a model API call; your assistant's own usage may have a cost.)*

- **Zero-Daemon Drop Folder:**
  Drop web shortcuts or notes into the Lectic Inbox folder reported by status. No separate folder watcher is required. Items appear when your connected assistant checks the library or inbox. Select items to sort; failed imports retain the original for a safe retry.

- **Apply compiled methods:**
  > Use my Debugging Starter to review this pull request architecture.

- **Share with teammates:**
  > I want to share my Engineering Standards with the team.
  
  *(Configure a signing identity, export a pack, and choose where to share it. A recipient who already has Lectic can say: `"Install this Lectic pack: [link]"`.)*

**Want to use it in hosted chat or your phone?** See the [cloud & phone guide](docs/CLOUD.md). `python -m lectic.cli share` provides an HTTPS connector while its server keeps running. Quick tunnels change address after restart. **Anyone with the link can read and change your knowledge; keep it private.** A chat attachment alone does not install Lectic tools.

---

## The 5 Superpowers

### 1. Zero-Daemon Drop Inbox
Drop Chrome/Edge shortcuts (`.url`), Safari shortcuts (`.webloc`), text notes (`.txt`, `.md`) and transcripts (`.vtt`, `.srt`) into the folder reported by status. A connected assistant checks the folder on demand. Syncing that folder through another service requires your own configuration; hosted connectors still need a running server.

### 2. Portable Knowledge Packs (`.lectic`)
Export any collection into a single, self-contained file (`lectic pack "Engineering Standards" --team`). Heuristics, decision rules, capability maps, and source citations travel together in one verifiable package.

### 3. Cryptographic Ed25519 Signatures
New signed packs use Ed25519. A valid signature establishes possession of the embedded key and detects changes to signed content. Check the publisher's fingerprint through a trusted channel to establish identity. Unsigned packs remain supported; the bundled starter is unsigned. Legacy HMAC signatures are labeled unverified.

### 4. Evidence Checks (`lectic verify`)
AI should show its work. `lectic verify` checks evidence excerpts, links, and source hashes, with a deterministic exit code (0 = verified, 1 = issues). This checks traceability, not whether a source is true or an interpretation is correct.

### 5. Team Distribution & 1-Command Onboarding
A lead engineer compiles team standards once. Teammates with Lectic installed or connected can install the pack and ask their assistant to apply it. Installation reports unavailable sources and partial verification explicitly. Pinning records a version; nothing auto-updates. Use `python -m lectic.cli update engineering` to request an update while preserving previous knowledge history.

---

## Supported Inputs & Formats

| Input Format | Processing & Behavior |
| --- | --- |
| **Pasted text & notes** | Saved immediately; processed when useful for an authorized task |
| **Transcripts (.txt, .md, .vtt, .srt)** | Parsed with timestamps and segmented for exact evidence citations |
| **Browser shortcuts (.url, .webloc)** | Drop into the Inbox folder reported by status; checked on demand |
| **YouTube links** | Captured instantly; available English captions fetched via optional `yt-dlp` |
| **Other web links** | Saved as references; no general article downloader |
| **PDF, images, audio, video** | Preserved as attachments; no built-in OCR or transcription |
| **Codex and Claude Code** | Automatic local MCP setup; restart once |
| **Other compatible MCP clients** | Manual configuration; see the installation guide |
| **Hosted chat and phones** | Running HTTPS connector required; anyone holding its private link can access the library |

---

## Portable Packs & Team Distribution

Share a collection with your engineering team, course students, or peers, with its evidence attached:

```bash
# Set your author signing identity
python -m lectic.cli identity set "Alex Rivera" --contact alex@platform.org

# Export a team pack (bundles full sources and Claude/Codex/ChatGPT install instructions)
python -m lectic.cli pack "Engineering Standards" --team --version 2.1.0 --out ./engineering-standards.lectic

# Publish to team storage (GitHub Releases, S3, R2, or HTTP PUT)
python -m lectic.cli publish ./engineering-standards.lectic --to https://github.com/org/repo
```

Recipients install with predictable naming and version pinning:
```bash
python -m lectic.cli install <download-url-from-publish> --as standards --pin
```

When standards evolve, team members update in place:
```bash
python -m lectic.cli update standards
```

---

Normal packs contain excerpts and source links. `--include-sources` bundles full originals you may redistribute; `--team` includes them by default, with `--exclude-sources` as an explicit override. Links-only installs can be partial if sources are inaccessible. Publishing rebuilds current collection content and verifies the recipient download; existing GitHub assets are preserved. Presigned PUT uploads also require a `--download-url`.

## Evidence You Can Inspect

Check the stored evidence before relying on a collection:

```bash
python -m lectic.cli verify "Engineering Standards"
```
The report identifies verified, partial, or broken evidence. You can use its exit code in CI; it cannot guarantee freedom from hallucinations or judge whether a method is appropriate for a task.

---

## Release & Quality Status

**0.3.1 is published as an alpha.** [Release notes](docs/RELEASE-0.3.1.md) detail the reliability improvements, Ed25519 signing, and offline starter. Get the [GitHub release](https://github.com/tyreamer/lectic/releases/tag/v0.3.1), [PyPI package](https://pypi.org/project/lectic/0.3.1/), or visit the [website and HTML pitch](https://tyreamer.github.io/lectic/).

- **Deterministic Traceability:** Lectic checks that citations and stored artifacts match their sources via content hashes. That establishes strict provenance—it does not replace human domain judgement.
- **Local storage:** New installations use `~/.lectic`, or `LECTIC_HOME` if configured. Existing legacy libraries are preserved. Knowledge backups merge additively; signing keys, cookies, and connector credentials are excluded and need separate private storage. A hosted connector stores knowledge on its host; your assistant's provider may receive material used in a task.
- **Open-Source Alpha:** Community feedback, issues, and contributions are welcome!

The real starter catalog currently contains one authored teaching pack. The test suite and installed-package checks establish workflow and evidence integrity. A completed comparative user study has not yet established improved task quality, retention, or willingness to pay. See the [evaluation protocol](docs/EVALUATION.md) and [original project review](docs/reviews/2026-09-25-project-review.md).

For contributors: [development guide](docs/DEVELOPING.md) · [architecture](DESIGN.md) · [MCP tools](docs/MCP.md) · [MIT license](LICENSE).
