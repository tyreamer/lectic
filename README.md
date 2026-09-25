<div align="center">

# Lectic

### Save what you trust. Your AI learns the method, not just the words.

[![Tests](https://github.com/tyreamer/lectic/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/lectic/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lectic?color=4b8bba)](https://pypi.org/project/lectic/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-4b8bba)](https://github.com/tyreamer/lectic/blob/main/LICENSE)
[![Marketplace](https://img.shields.io/badge/marketplace-registry-67e7db)](https://tyreamer.github.io/lectic/registry.html)

**[Start](#start)** · **[What it does](#what-it-does)** · **[Packs & Team Distribution](#portable-packs--team-distribution)** · **[Marketplace](#expertise-marketplace)** · **[Evidence Proof](#the-evidence-guarantee)** · **[Status](#current-status)**

Works with **Claude Code** · **Codex** · **ChatGPT** · **Claude Desktop** · **Cursor** · any MCP client

</div>

Most AI forgets everything the moment you close a chat. If you find a great video, lesson, or guide from someone who really knows their craft, you end up re-pasting transcripts forever or settling for generic AI advice.

Lectic fixes this. You save videos, articles, and transcripts once. Lectic turns that material into reusable, evidence-anchored tools—checklists, reviewers, diagnosis guides, and lessons—traceable back to the author's exact words. Save it once; use it across ChatGPT, Claude, Codex, Claude Code, and your phone.

---

## Start

### 1. Ask your assistant to set it up
Paste this into Claude Code, Codex, or any agent with terminal access:

> Set up Lectic for me: https://github.com/tyreamer/lectic

It reads [AGENTS.md](https://github.com/tyreamer/lectic/blob/main/AGENTS.md) and handles everything: installs the package, sets up signing identity, hooks up MCP tools, and tests the connection.

### 2. Or install it yourself in 30 seconds

```bash
pip install lectic
lectic setup
```

`lectic setup` configures your local assistants automatically, generates your cryptographic signing key, and offers YouTube caption support.

### 3. Talk naturally to your assistant

Open any connected assistant and speak in plain English:

> Save this YouTube talk to my engineering collection: https://www.youtube.com/watch?v=…

> Search the pack registry for distributed systems.

> Install the distributed-systems pack from the registry.

> Use my engineering standards to review this pull request architecture.

> I want to share my engineering standards with my team.

You can also drag browser tabs, drop `.url` shortcuts, or save text notes directly into your `Documents/Lectic Inbox` folder—no background servers or daemons required. When you next chat with your AI, it will notice your dropped items and ask where you'd like them filed.

Run `lectic status` anytime to see what's saved, connected, and waiting in your inbox.

**Want to use it in ChatGPT on the web, Claude, or your phone?** Run:
```bash
lectic share
```
This generates a private, secure link you can plug into ChatGPT Actions or an iPhone Share Sheet Shortcut ([cloud & phone guide](https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md)).

---

## What it does

- **Zero-Daemon Drop Folder & Intelligent Intake.** Drag browser tabs, `.url` shortcuts, or notes directly into your `Documents/Lectic Inbox` folder without keeping background processes or servers alive. When you chat with your AI, Lectic analyzes creators and keywords, identifies intelligent candidate collections, and routes them with your confirmation.
- **Pure Conversational Sharing & 1-Command Onboarding.** Tell your AI "Share my engineering standards." It packages everything—heuristics, rules, and source evidence—into a signed pack and gives you a 1-sentence prompt for your teammate: *"Install this Lectic pack: [link]"*. When your teammate pastes that into Claude Code, Codex, or ChatGPT, their AI immediately adopts your standards.
- **Portable Knowledge Packs (`.lectic`).** Export your collection into a single, signed file (`lectic pack "Engineering Standards" --team`). Knowledge units, decision rules, capability maps, and evidence excerpts travel together in one verifiable package.
- **The Expertise Marketplace.** Discover, inspect, and install community and team packs by name (`lectic search`, `lectic inspect registry:NAME`, `lectic install registry:NAME`). Browse the web marketplace at [tyreamer.github.io/lectic/registry.html](https://tyreamer.github.io/lectic/registry.html).
- **The Evidence Guarantee (`lectic verify`).** AI should show its work. Every unit of knowledge in Lectic is anchored to an exact substring in the source transcript. `lectic verify` checks evidence integrity with a deterministic exit code (0 = verified, 1 = broken), ready for CI pipelines.
- **Cryptographic Author Identity.** Packs are signed with author credentials (`lectic identity set "Name" --contact email`). Recipients verify who compiled the pack and know that its contents haven't been tampered with.
- **Local-First & Zero Vendor Lock-in.** Your knowledge lives in `~/.lectic`. Back up everything with `lectic backup`, restore anywhere with `lectic restore`, or sync across machines with `lectic push`/`pull`.

---

## Portable Packs & Team Distribution

Share a collection with your engineering team, course students, or peers with complete evidence guarantees.

```bash
# Set your author signing identity
lectic identity set "Alex Rivera" --contact alex@platform.org

# Export a team pack (bundles full sources and Claude/Codex/ChatGPT install instructions)
lectic pack "Engineering Standards" --team --version 2.1.0

# Publish to team storage (GitHub Releases, S3, R2, or HTTP PUT) with webhook alerts
lectic publish "Engineering Standards" --to https://github.com/org/repo --webhook https://hooks.slack.com/...
```

Recipients install with predictable naming and version pinning:
```bash
lectic install https://github.com/org/repo/releases/download/v2.1.0/standards.lectic --as standards --pin
```

When standards evolve, team members update with one command:
```bash
lectic update standards
# -> Updated standards from 2.0.0 to 2.1.0 (3 new conventions added, 1 modified)
```

---

## Expertise Marketplace

Lectic includes a decentralized, Homebrew/Cargo-style registry ([`registry/index.json`](https://github.com/tyreamer/lectic/blob/main/registry/index.json)) hosting verified domain expertise packs.

### Search and inspect from the CLI
```bash
# Search available packs by keyword or category tag
lectic search engineering
lectic search --tag architecture

# Preview evidence, methods, and README before installing
lectic inspect registry:distributed-systems-adr

# Install with version pinning
lectic install registry:distributed-systems-adr --as distributed-systems --pin
```

### Or search via your AI assistant
All connected assistants have native MCP access to `lectic_search` and `lectic_inspect`:
> "Find me a verified pack for FIFA market trading and install it."

### Publish your own pack to the marketplace
1. Compile and sign your pack: `lectic pack my-topic --team`
2. Generate registry entry: `lectic publish my-topic --to <URL> --registry`
3. Submit a Pull Request adding the JSON entry to `registry/index.json` in [`tyreamer/lectic`](https://github.com/tyreamer/lectic).

Browse the interactive web catalog at [**tyreamer.github.io/lectic/registry.html**](https://tyreamer.github.io/lectic/registry.html).

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

Run `lectic verify` in GitHub Actions or your pre-commit hooks to guarantee that your AI tools never act on broken or hallucinated heuristics.

---

## CLI Reference

| Command | Description |
| --- | --- |
| `lectic setup` | Configure local assistants, signing identity, and YouTube support |
| `lectic identity` | Show or configure the cryptographic author signing key (`--contact`) |
| `lectic search [QUERY]` | Search the pack registry for verified expertise (`--tag`, `--json`) |
| `lectic inspect TARGET` | Preview manifest, methods & README without installing (`registry:NAME`, file, URL) |
| `lectic install TARGET` | Install pack into knowledge home (`--as NAME`, `--pin`, `registry:NAME`) |
| `lectic update NAME` | Check pack origin for newer releases and update in-place (`--force`) |
| `lectic pack NAME` | Compile collection into shareable `.lectic` file (`--team`, `--version`) |
| `lectic publish NAME` | Upload pack to team host or community registry (`--to`, `--registry`, `--webhook`) |
| `lectic verify [NAME]` | Deterministic CI check for evidence linkage (exit 0 = verified, 1 = issues) |
| `lectic share` | Generate a private link for ChatGPT, Claude web, or phone shortcuts |
| `lectic backup` | Package all collections, sources, and builds into a single archive file |
| `lectic restore FILE` | Restore an archive into the local knowledge home |
| `lectic push / pull LINK` | Sync knowledge between two Lectic servers |
| `lectic status` | View saved collections, connected assistants, and evidence health |

---

## Current Status

| Area | Available today | Boundary |
| --- | --- | --- |
| **Packs & Distribution** | Signed `.lectic` archives, `--team` bundling, `--pin`, `INSTALL.md`, GitHub/S3 upload, webhooks | Distribution requires an author-managed file host (GitHub, S3, R2, etc.) |
| **Marketplace** | Decentralized `registry/index.json`, `lectic search`, `lectic inspect`, web UI at `registry.html` | Submissions reviewed via GitHub Pull Requests |
| **Evidence Guarantee** | `lectic verify` deterministic check (exit code 0/1), HMAC-SHA256 author signing | Confirms exact textual citation support; does not evaluate subjective opinion |
| **Intelligent Intake** | Creator and topic matching, candidate collection suggestions, interactive prompt | Deferred YouTube captions via `yt-dlp`; text and transcript uploads |
| **Assistant Protocol** | Universal MCP server (stdio and streamable HTTP) for Claude Code, Codex, ChatGPT, Cursor | Single-user local server architecture |
| **Storage & Backup** | Local-first in `~/.lectic`, full archive backups (`backup`/`restore`), live server sync (`push`/`pull`) | Multi-tenant user permissioning is out of scope |

---

## Documentation

| Guide | Purpose |
| --- | --- |
| [Web Marketplace](https://tyreamer.github.io/lectic/registry.html) | Interactive catalog of verified knowledge packs |
| [Packs & Team Distribution](https://github.com/tyreamer/lectic/blob/main/docs/PACKS.md) | Creating, signing, distributing, and updating `.lectic` packs |
| [MCP Server](https://github.com/tyreamer/lectic/blob/main/docs/MCP.md) | Connect Claude Code, Codex, ChatGPT, or custom MCP clients |
| [Anywhere](https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md) | ChatGPT, Claude web, Gemini, and iPhone Share Sheet setup |
| [CLI Reference](https://github.com/tyreamer/lectic/blob/main/docs/CLI.md) | Complete flag and command specifications |
| [YouTube Retrieval](https://github.com/tyreamer/lectic/blob/main/docs/YOUTUBE.md) | Retrieve and timestamp YouTube captions on demand |
| [Capture Details](https://github.com/tyreamer/lectic/blob/main/docs/CAPTURE.md) | Ingestion states, background sync, and folder imports |
| [Architecture & Design](https://github.com/tyreamer/lectic/blob/main/DESIGN.md) | Compiler design, schemas, and verification internals |
| [Contributing & Developing](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md) | Running tests, code organization, and PR guidelines |

---

## Contributing

Contributions including reproducible test cases, evidence extractors, and registry packs are welcome! See the [development guide](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md).

Run the full test suite:
```bash
python -m unittest discover -s tests -v
```

## License

[MIT](https://github.com/tyreamer/lectic/blob/main/LICENSE). Imported content retains its original ownership and licensing.
