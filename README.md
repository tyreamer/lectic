<div align="center">

# Lectic

### Save what you trust. Your AI learns the method, not just the words.

[![Tests](https://github.com/tyreamer/lectic/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/lectic/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lectic?color=38bdf8)](https://pypi.org/project/lectic/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399)](https://github.com/tyreamer/lectic/blob/main/LICENSE)
[![Signatures: Ed25519](https://img.shields.io/badge/signatures-Ed25519-a78bfa)](https://github.com/tyreamer/lectic/blob/main/docs/PACKS.md)
[![Catalog](https://img.shields.io/badge/starter-shelf-38bdf8)](https://tyreamer.github.io/lectic/registry.html)

**[Quickstart](#quickstart-in-10-seconds)** · **[How it Works](#how-it-works)** · **[Daily Flow](#talk-naturally-to-your-assistant)** · **[Core Superpowers](#the-5-superpowers)** · **[Packs & Teams](#portable-packs--team-distribution)** · **[Status](#release--quality-status)**

Works with **Claude Code** · **OpenAI Codex** · **ChatGPT** · **Claude Desktop** · **Cursor** · any MCP client

</div>

---

### The Problem

Every chat with an AI assistant starts from zero.

You watch a brilliant 40-minute engineering talk, find a definitive architecture decision record (ADR), or study a debugging postmortem. You paste it into Claude or ChatGPT, get an insightful answer, and close the tab.

**Tomorrow, the AI forgets everything.** You're back to re-pasting excerpts, re-prompting context, or settling for generic chatbot fluff.

### The Solution

**Lectic fixes this.** Save the videos, articles, and transcripts you trust once. Lectic compiles them into portable, cryptographically signed `.lectic` knowledge packs—anchoring every decision rule, reviewer method, and checklist directly back to the author's exact words.

Save it once; your AI applies the methods across Claude Code, Codex, ChatGPT, and your team forever.

---

## Quickstart in 10 Seconds

### 1. Ask your assistant to set it up (Zero-command install)
Paste this into **Claude Code** or **OpenAI Codex**:

> Set up Lectic for me: https://github.com/tyreamer/lectic

It reads [AGENTS.md](AGENTS.md) and handles everything: installs the package, sets up your Ed25519 signing identity, hooks up MCP tools, and verifies the connection. **Restart your assistant once** after setup.

### 2. Try the instant offline starter
Say to your assistant:

> Try Lectic with its offline debugging starter.

The bundled teaching pack produces a source-backed review of a sample debugging plan and a reusable checklist citing real procedures—**running 100% offline without API keys or downloads**.

Then try your own work:
> Use my Debugging Starter to review this plan: [paste your plan]

### 3. Or install via terminal in 30 seconds

```bash
pip install --upgrade lectic
lectic setup --yes
lectic try
```

Run `lectic status` anytime to see your knowledge folder, inbox, and connection health.

---

## Talk Naturally to Your Assistant

Open any connected assistant and speak in plain English:

- **Save without friction:**
  > Save this for later: https://www.youtube.com/watch?v=…
  
  *(Goes straight to **Inbox**—no mandatory categorization, no API costs.)*

- **Zero-Daemon Drop Folder:**
  Drag browser tabs from Chrome, Edge, or Safari, or drop notes directly into your `Documents/Lectic Inbox` folder. No background server or daemon needed. When you next chat with your AI, it surfaces what you dropped:
  > *"I noticed you dropped a link to an engineering talk into your Lectic folder. Would you like me to add it to your 'Architecture' collection?"*

- **Apply compiled methods:**
  > Use my Debugging Starter to review this pull request architecture.

- **Share with teammates:**
  > I want to share my Engineering Standards with the team.
  
  *(Assistant creates a signed pack and gives a 1-sentence prompt for your teammate: `"Install this Lectic pack: [link]"`.)*

**Want to use it in ChatGPT on the web or your phone?** Run `lectic share` to generate a secure link for ChatGPT Actions or an iPhone Share Sheet Shortcut ([cloud & phone guide](docs/CLOUD.md)).

---

## The 5 Superpowers

### 1. Zero-Daemon Drop Inbox
No localhost server listening on a port to fail when your laptop sleeps. Drag tabs from Chrome/Edge (`.url`), Safari (`.webloc`), or drop text notes (`.txt`, `.md`) and transcripts (`.vtt`, `.srt`) directly into `Documents/Lectic Inbox`. Syncs between phone and computer effortlessly via iCloud or OneDrive.

### 2. Portable Knowledge Packs (`.lectic`)
Export any collection into a single, self-contained file (`lectic pack "Engineering Standards" --team`). Heuristics, decision rules, capability maps, and source citations travel together in one verifiable package.

### 3. Cryptographic Ed25519 Signatures
Packs are signed using asymmetric Ed25519 keypairs. Recipients verify author provenance and tamper-proof integrity without sharing private secrets.

### 4. The Evidence Guarantee (`lectic verify`)
AI should show its work. Every unit of knowledge in Lectic is anchored to an exact substring in the source transcript. `lectic verify` checks evidence integrity with a deterministic exit code (0 = verified, 1 = broken), ready for CI pipelines.

### 5. Team Distribution & 1-Command Onboarding
A lead engineer compiles team standards once. Team members run `lectic install <url> --as engineering --pin` and immediately work inside the team's conventions across Claude Code, Codex, and ChatGPT. When standards evolve, teammates update with one command: `lectic update engineering`.

---

## Supported Inputs & Formats

| Input Format | Processing & Behavior |
| --- | --- |
| **Pasted text & notes** | Saved immediately; processed when useful for an authorized task |
| **Transcripts (.txt, .md, .vtt, .srt)** | Parsed with timestamps and segmented for exact evidence citations |
| **Browser drag-and-drop (.url, .webloc)** | Saved to `Documents/Lectic Inbox` without needing background daemons |
| **YouTube links** | Captured instantly; available English captions fetched via optional `yt-dlp` |
| **Codex, Claude Code, Cursor** | Native Model Context Protocol (MCP) stdio connection |
| **ChatGPT & Mobile (iPhone / Android)** | Secure authenticated streaming HTTP connector (`lectic share`) |

---

## Portable Packs & Team Distribution

Share a collection with your engineering team, course students, or peers with complete evidence guarantees:

```bash
# Set your author signing identity
lectic identity set "Alex Rivera" --contact alex@platform.org

# Export a team pack (bundles full sources and Claude/Codex/ChatGPT install instructions)
lectic pack "Engineering Standards" --team --version 2.1.0

# Publish to team storage (GitHub Releases, S3, R2, or HTTP PUT)
lectic publish "Engineering Standards" --to https://github.com/org/repo
```

Recipients install with predictable naming and version pinning:
```bash
lectic install https://github.com/org/repo/releases/download/v2.1.0/standards.lectic --as standards --pin
```

When standards evolve, team members update in place:
```bash
lectic update standards
# -> Updated standards from 2.0.0 to 2.1.0 (3 new conventions added, 1 modified)
```

---

## The Evidence Guarantee

Unlike generic vector databases or RAG pipelines that summarize blindly, Lectic deterministically tracks every claim back to the author's exact words:

```bash
lectic verify "Engineering Standards"
```
```text
Verification: Engineering Standards
  Overall: verified (exit 0)
  Units:   38 verified, 0 broken citations
  Sources: 4 of 4 sources verified against content hashes
```

Run `lectic verify` in GitHub Actions or pre-commit hooks to guarantee your AI tools never act on broken or hallucinated heuristics.

---

## Release & Quality Status

The source tree is currently preparing **0.3.1**. [Release notes](docs/RELEASE-0.3.1.md) detail recent reliability enhancements, Ed25519 signing, and offline starter integration.

- **Deterministic Traceability:** Lectic checks that citations and stored artifacts match their sources via content hashes. That establishes strict provenance—it does not replace human domain judgement.
- **Local-First & Zero Vendor Lock-in:** Your knowledge lives in `~/.lectic`. Back up everything with `lectic backup`, restore anywhere with `lectic restore`.
- **Open-Source Alpha:** Community feedback, issues, and contributions are welcome!

For contributors: [development guide](docs/DEVELOPING.md) · [architecture](DESIGN.md) · [MCP tools](docs/MCP.md) · [MIT license](LICENSE).
