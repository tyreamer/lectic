<div align="center">

# Lectic

### Save what you trust. Your AI learns the method, not just the words.

[![Status: Alpha](https://img.shields.io/badge/status-alpha-f0b44d)](#current-status)
[![License: MIT](https://img.shields.io/badge/license-MIT-4b8bba)](https://github.com/tyreamer/lectic/blob/main/LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)

**[Start](#start)** · **[What it does](#what-it-does)** · **[Examples](#what-you-can-build)** · **[How it works](#how-it-works)** · **[Status](#current-status)**

</div>

You watch a great talk, read a course, keep a transcript from someone who really knows their craft. Lectic turns that material into expertise your assistant can *apply*: reviewers, checklists, decision frameworks, lessons — each one traceable back to the exact words that support it. Save once; every assistant and every project on your machine can use it.

## Start

```bash
pip install lectic
lectic setup
```

`lectic setup` connects Claude Code and Codex if they are installed, verifies the connection, and offers YouTube support. Then open either assistant, in any folder, and talk:

> Save this for later: https://www.youtube.com/watch?v=…

> What could my saved material become?

> Use my Sales Training to review this call transcript.

That's the whole interface. No commands to learn, no goal to invent up front, nothing to re-upload later. `lectic status` shows where your knowledge lives and what is connected.

**Use ChatGPT, Claude on the web, or Gemini?** One more command gives them the same knowledge:

```bash
lectic share
```

It prints a private link and where to paste it. Your phone can post captures to the same link. To keep the link up when the laptop is closed, run the same server always-on ([guide](https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md)). Windows and macOS alike; Python 3.10+ is the only requirement.

<details>
<summary>Prefer an installed skill?</summary>

The installed skill (`/lectic` in Claude Code, `$lectic` in Codex) drives the same compiler through your assistant's file access and remains supported; see [installation](https://github.com/tyreamer/lectic/blob/main/docs/INSTALLATION.md).

</details>

## What it does

**Saving is free.** Share a link, paste text, or point at a folder of transcripts. Nothing is processed until you want something from it, and your reason for saving stays separate from the source.

**You don't need a plan.** Ask what a collection could become and Lectic returns a ranked map of concrete jobs it can support: what you'd give it, what you'd get back, and where the evidence runs out. Pick one and it builds it.

**Results carry their evidence.** A review, a checklist, a lesson, a decision — every point cites the source passage behind it, and source statements stay distinct from the assistant's inference.

**Build once, reuse everywhere.** A method built from your Sales Training today reviews a different call tomorrow, from ChatGPT, Claude, Gemini, Codex or Claude Code, in any project, with no re-upload. Add sources later and earlier work is preserved.

**Share what you know.** `lectic pack "FC 27"` turns a collection into one file. Anyone runs `lectic install` on it and every assistant they use can apply it. Sources travel as links and are verified on the installer's own network, so nothing is redistributed ([packs →](https://github.com/tyreamer/lectic/blob/main/docs/PACKS.md)).

## What you can build

| Material | Useful capability | Give it → get back |
| --- | --- | --- |
| Photography lessons | **Portrait Critic** | Portrait and settings → focus/motion checks and a retake plan |
| Sales training | **Discovery Call Reviewer** | Call transcript → missed questions and concrete follow-ups |
| Architecture talks | **Architecture Review Checklist** | Access-control design → scoped issues and verification steps |
| Business strategy lessons | **Market Decision Framework** | Market hypotheses → conditional comparison and missing evidence |

**Capabilities follow the evidence.** If the material lacks procedures, criteria, examples or conditions, the map says so instead of inventing them. These examples come from small synthetic fixtures and illustrate the kinds of transformation supported, not measured effectiveness. [Explore the fixtures →](https://github.com/tyreamer/lectic/blob/main/fixtures/opportunities/README.md)

## How it works

```mermaid
flowchart TD
    A[Capture or import] --> B[Source collection]
    B --> C[Durable expertise IR]
    C --> D[Capability Map or user goal]
    D --> E[Compiled method]
    E --> F[Text result or skill artifact]
    F --> G[Structure and evidence validation]
    G -. Optional facilitated comparison .-> H[Evaluate and refine]
```

The **Expertise IR** is the durable asset. Capability Maps are versioned interpretations of it; methods and outputs are builds from it. The MCP server and the installed skill are two interfaces to the same compiler, and Agent Skills is one output target. The core remains independent of a particular AI provider.

Knowledge lives in one **Lectic home** per user (`~/.lectic`, or `LECTIC_HOME`): original sources as content-addressed blobs, normalized segments, knowledge revisions, maps, private briefs and saved builds. Interrupted workflows retain checkpoints. Every project and every assistant on the machine sees the same collections. A project that already contains a `.expertise-compiler/` folder keeps using it; ask “Where does Lectic store my knowledge?” to see which applies.

[Architecture and remaining boundaries →](https://github.com/tyreamer/lectic/blob/main/DESIGN.md)

## Capture now, use later

Save things as you meet them, with a reason if you have one, and sort them into collections later or never:

> Save this architecture talk. Great on permission boundaries, but don't treat it as company policy.

> Use my AI Architecture collection to review this design.

Saving stores exactly what you shared and your note, nothing more. Processing happens when a use needs it. YouTube links become English captions on request (through `yt-dlp`, which `lectic setup` offers to install); other links stay saved as links. Lectic does not fetch article bodies, parse PDFs, OCR images, scrape social platforms or transcribe audio, and an unavailable caption stays a visible gap rather than a made-up summary.

From a phone, a two-action Share Sheet Shortcut posts straight to your Lectic link ([guide](https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md#your-phone)); a [synced-folder Shortcut](https://github.com/tyreamer/lectic/blob/main/docs/iphone-shortcut.md) remains for phones that cannot reach it.

[Capture contract, states and sync details →](https://github.com/tyreamer/lectic/blob/main/docs/CAPTURE.md)

## Current status

| Area | Available today | Boundary |
| --- | --- | --- |
| Processing | Text/transcript files and deferred YouTube English-caption retrieval | Optional `yt-dlp` required for YouTube; no arbitrary URL or audio/video acquisition |
| Discovery | Grounded, ranked Capability Maps with version history | Quality depends on source support and assistant interpretation |
| Outputs | Reusable text methods, work products, optional skill exports, shareable knowledge packs | No standalone agent runtime or persistent coaching service |
| Capture | Phone or assistant posts to `/capture`; synced-folder import; annotations and multiple memberships | Saving stores what was shared; only YouTube captions are retrieved, on request |
| Validation | Schemas, hashes, evidence references and artifact structure | Does not establish sound judgment or effectiveness |
| Evaluation | Matched prompts, structured checks and effort records | Independent runs, human review and refinement need coordination |

**Your knowledge, your server, any assistant.** No hosted backend you don't control, no model API key: your assistant does the reasoning under its own subscription, and Lectic keeps the results honest and reusable. `lectic share` or an always-on container gives ChatGPT, Claude, Gemini and your phone the same home through one private link.

### Toward portable knowledge

One knowledge store reachable from a phone, ChatGPT, Claude, Gemini, Codex and Claude Code alike, with local storage as the offline/private mode rather than the only mode. In place: one home per user behind a storage seam built for object storage ([design →](https://github.com/tyreamer/lectic/blob/main/DESIGN.md#storage-one-home-cloud-shaped)); an [MCP server](https://github.com/tyreamer/lectic/blob/main/docs/MCP.md) over stdio and Streamable HTTP so any client operates the compiler through validated tools; `lectic share`, an always-on container and phone capture over one private link ([guide →](https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md)). Still ahead: a remote object store behind the seam so several machines can share one home without one of them being the server, and a published PyPI release.

## Test the idea with us

The automated suite covers provenance, revisions, capture, discovery, builds and reuse across unrelated fixtures. Semantic fixture answers are authored test data; they are not evidence that the compiler outperforms ordinary chat.

We are testing with **AI builders, consultants, creators and knowledge-heavy professionals**. The study includes fair baseline comparisons, fresh-session reuse, source changes and refinement on unseen tasks.

**[Start with the concept-validation guide →](https://github.com/tyreamer/lectic/blob/main/docs/testing-guide.md)**

## Documentation

| Guide | Purpose |
| --- | --- |
| [Installation](https://github.com/tyreamer/lectic/blob/main/docs/INSTALLATION.md) | Setup, updates and troubleshooting |
| [MCP server](https://github.com/tyreamer/lectic/blob/main/docs/MCP.md) | Connect Claude Code, Codex or any MCP client; tools and write policy |
| [Anywhere](https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md) | ChatGPT, Claude, Gemini, your phone, a second computer: one private link |
| [Packs](https://github.com/tyreamer/lectic/blob/main/docs/PACKS.md) | Share a collection as one file; install someone else's |
| [YouTube retrieval](https://github.com/tyreamer/lectic/blob/main/docs/YOUTUBE.md) | Paste links, retrieve captions on demand, preserve evidence and reuse it |
| [Guided use](https://github.com/tyreamer/lectic/blob/main/docs/GUIDED-USE.md) | See what is saved, discover concrete applications and reuse it |
| [iPhone Shortcut](https://github.com/tyreamer/lectic/blob/main/docs/iphone-shortcut.md) | Capture setup and exact first live test |
| [Evaluation](https://github.com/tyreamer/lectic/blob/main/docs/EVALUATION.md) | Compare against capable ordinary transcript chat |
| [Architecture](https://github.com/tyreamer/lectic/blob/main/DESIGN.md) | Current boundaries, storage and limitations |
| [North star](https://github.com/tyreamer/lectic/blob/main/NORTH_STAR.md) | Product direction and extensible build targets |
| [Development](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md) | Code structure, tests and contribution workflow |
| [CLI reference](https://github.com/tyreamer/lectic/blob/main/docs/CLI.md) | Deterministic utilities operated by the assistant |

## Contributing

Useful contributions include reproducible failures, evidence-quality improvements and observations from real tasks. Follow the [development guide](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md) and preserve the separation between source content, personal context, expertise and builds.

Run the existing suite from a checkout:

```sh
python -m unittest discover -s tests -v
```

[Report an issue](https://github.com/tyreamer/lectic/issues) with a minimal, sanitized example. Keep private corpora and client work out of public reports.

## License

[MIT](https://github.com/tyreamer/lectic/blob/main/LICENSE). Imported content retains its original ownership and licensing; a citation does not grant redistribution rights.
