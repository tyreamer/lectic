# Lectic

Turn sources into a reusable knowledge pack. Make something useful, share the pack, and let someone else make something different.

[![Tests](https://github.com/tyreamer/lectic/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/lectic/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lectic?color=38bdf8)](https://pypi.org/project/lectic/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399)](https://github.com/tyreamer/lectic/blob/main/LICENSE)

Start in the AI chat you already use. Lectic distills your sources into context you can reuse across tasks, conversations and people. The library helps you inspect and share that knowledge.

The connected agent helps you spot useful next steps: how a pack fits your current goal, which saved knowledge could help with new work, and who might benefit from a particular pack. It recommends one starting use with up to two alternatives, carries your chosen direction forward, and keeps quick saves brief. Personal context stays separate from source evidence; sharing suggestions never send anything automatically. See the [agent guidance](prompts/proactive-guidance.md).

With Lectic connected, send your sources and ask:

> Save these sources in Lectic and distill them into a reusable context pack. Based on what you know about me and what I'm working on, suggest three useful ways to use it. Help me choose one and make something useful.

Already have a pack? Attach its readable context export in ChatGPT, Claude or Gemini and ask:

> Based on what you know about me, how could I use this context? Help me pick a useful starting point.

Saving and compiling through chat requires a connection; a prompt alone does not install or connect Lectic. Codex and Claude Code can perform local setup. Hosted assistants need a reachable Lectic connection where supported, or a readable pack file. See [setup](#how-to-set-it-up) and [remote connections](docs/CLOUD.md).

## Web pilot — available for local review

Bring links, files and notes together, then distill them into a **context pack**: reusable knowledge with its source evidence. Open the pack for a recommended starting use and up to two alternatives, with a short reason to start there. Add what you are working on to get suggestions for your situation, or describe your own idea. Creations use real model calls and include expandable source references.

You can also download the pack as a readable context file, attach it in ChatGPT or Claude, and ask: **“Based on what you know about me, how could I use this?”** Share the pack so someone else can use the same knowledge differently. `.lectic` downloads remain available; advanced options include reusable prompts, agent skills and a local read-only MCP server bundle.

Your library starts empty. **Customer Discovery Guide**, **Code Debugging Playbook**, and **Startup Principles** are optional Lectic-authored teaching examples under MIT. Browsing does not install anything; adding an example is an explicit choice.

The implementation includes a React app, FastAPI service, durable worker, account-scoped storage, cost reservations, media processing, multi-source packs, fixed-version share links, and Swift/Kotlin capture companions. The existing local compiler and `.lectic` format remain supported.

**Release status:** this is a local pilot implementation, not a publicly available hosted service. Dedicated cloud accounts, configured Google/Apple sign-in, iOS signing and device checks, real hosting retrieval measurements, and the ten-person usability study remain launch gates. No cloud resources have been provisioned. See [pilot setup, evidence and limitations](docs/PILOT.md).

Personal chat connections are now implemented for local verification: **Connect AI → sign in and approve → give your AI your own sources → build and reuse a pack**. The authenticated MCP endpoint uses the same personal library and durable processing as the web app, with revocable connections and proactive guidance. Hosted activation and real ChatGPT/Claude/Gemini interoperability checks still require the dedicated cloud accounts. See the [personal connection guide and launch checks](docs/PERSONAL_CHAT.md). Additional library and mobile features should wait until this primary route proves useful.

Public Instagram/X retrieval is best effort. An incomplete post stays **Needs content** with **Add screenshots or video**; a caption or thumbnail never stands in for the complete post. Uploaded media uses automatic transcripts/OCR and sampled video frames, with those derivations labeled separately.

Download a starter: [Customer Discovery](docs/packs/customer-discovery.lectic) · [Code Debugging](docs/packs/debugging-starter.lectic) · [Startup Principles](docs/packs/startup-principles.lectic).

---

## What Lectic does

A useful conversation should not force you to gather and explain the same sources again for the next task. Lectic keeps distilled knowledge and its evidence together in a reusable pack. Your assistant can apply it to a new goal, inspect the original passage, or share the same context with someone else.

---

## How to set it up

### 1. Ask your assistant to set it up

If you use Claude Code or OpenAI Codex, paste this sentence into your chat:

> Set up Lectic for me: https://github.com/tyreamer/lectic

Your assistant will download Lectic and connect to it automatically. When it finishes, restart your assistant once so it can use its new tools.

### 2. Start with your own sources

Send your assistant the sources you want to use and the starting prompt above. Ask it to create one useful result, then reuse the same pack for a different task. Your Lectic starts empty; examples are only added when you request one.

For an optional offline example, say:

> Try Lectic with its offline debugging starter.

Lectic creates a test collection containing three sentences from a sample debugging lesson. It reviews a sample plan using those sentences and prints the exact quotes. This test runs on your computer without downloading anything or calling an external API.

### 3. Or install it using your terminal

If you prefer to install it yourself, run these commands in your terminal:

```bash
pip install --upgrade lectic
lectic setup --yes
lectic try
```

You can run `lectic status` at any time to see where your files are saved and which assistants are connected.

---

## How to use it every day

### 1. Save files and links

You can tell your assistant:

> Save this video: https://www.youtube.com/watch?v=24JAM7BACtA

Your assistant saves the link to your Inbox folder. If you give the name of a collection, it puts the link into that collection.

You can also drag web links from Chrome, Edge, or Safari directly into the `Documents/Lectic Inbox` folder on your computer. You can also drop text files (`.txt`, `.md`) and transcript files (`.vtt`, `.srt`) into that folder. Lectic does not need a background app running to notice these files. The next time you open your assistant, it will tell you what files are waiting in your folder and ask where you want to put them.

### 2. Ask questions about what you saved

You can ask your assistant to read your saved files and answer questions:

> What does my debugging video say about fixing parser bugs?

Your assistant reads your saved transcript, summarizes the advice, and quotes the exact sentence and timestamp:

> According to Ada in debugging-lesson.vtt at 00:09, "Change one suspected cause at a time, rerun the same input, and compare the result."

### 3. Share collections with coworkers

You can export a collection into a single `.lectic` file to share with other people:

```bash
# 1. Set your name and email address so recipients know who created the file
lectic identity set "Alex Rivera" --contact alex@example.com

# 2. Export your collection into a single file
lectic pack "Engineering Standards" --team

# 3. Send that file to a coworker. They install it by running:
lectic install engineering-standards.lectic --as standards --pin
```

When your coworker asks their assistant about engineering standards, their assistant will search and quote the same material. When you update the file, your coworker can run `lectic update standards` to get the latest version.

---

## Supported files

| File type | What Lectic does with it |
| --- | --- |
| **YouTube links** | Saves the link and downloads English captions automatically if they are available. |
| **Notes and text files (.txt, .md)** | Saves the text and splits it into searchable sections. |
| **Video and audio transcripts (.vtt, .srt)** | Saves the text along with timestamps so your AI can quote exact minutes and seconds. |
| **Browser links (.url, .webloc)** | Reads the web address when you drag a tab from your browser into your Lectic folder. |

Other web pages are saved as links for your reference. Lectic does not download full article text from general websites.

---

## Checking your files

You can check whether every quote in a collection still matches the original file text by running:

```bash
lectic verify "Engineering Standards"
```

If all quotes match their sources, Lectic prints `verified` and exits with code 0. If a quote was edited, deleted, or its source file was moved, Lectic prints which quote failed and exits with code 1. You can run this command in automated test scripts to make sure your AI never quotes broken sources.

---

## Where your files are kept

All of your saved files, notes, and collections are stored in a folder called `.lectic` in your user directory (for example, `C:\Users\YourName\.lectic` on Windows or `/Users/yourname/.lectic` on macOS). Lectic does not send your files to a cloud server. Your data stays on your computer.

If you want to use Lectic with ChatGPT on the web or on your phone, you can run `lectic share` to create a temporary, password-protected web address. Anyone who has that address can read your saved files, so keep that address private.

---

## Contributing and license

Lectic is open-source software licensed under the MIT license.

For technical details, read the [developer documentation](docs/DEVELOPING.md), the [architecture notes](DESIGN.md), and the [MCP tool reference](docs/MCP.md).
