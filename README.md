# Lectic

Save videos and notes on your computer so your AI assistant can search them and quote them.

[![Tests](https://github.com/tyreamer/lectic/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/lectic/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lectic?color=38bdf8)](https://pypi.org/project/lectic/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399)](https://github.com/tyreamer/lectic/blob/main/LICENSE)

Works with Claude Code, OpenAI Codex, ChatGPT, Claude Desktop, and Cursor.

---

## What Lectic does

When you paste text or a video link into a chat with an AI, the AI forgets that information as soon as you close the conversation.

Lectic saves your links, notes, and video transcripts into folders on your computer. When you ask your AI a question, it searches those saved files, writes an answer based on what you saved, and shows you the exact sentence and timestamp from the original source.

---

## How to set it up

### 1. Ask your assistant to set it up

If you use Claude Code or OpenAI Codex, paste this sentence into your chat:

> Set up Lectic for me: https://github.com/tyreamer/lectic

Your assistant will download Lectic and connect to it automatically. When it finishes, restart your assistant once so it can use its new tools.

### 2. Try an offline test

Say this to your assistant:

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
