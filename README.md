# WayKit

*Turn material you trust into reusable expertise for your AI assistant.*

> **Note:** WayKit was previously known as Lectic. Legacy commands (`lectic`), pack formats (`.lectic`), and storage paths (`.lectic`) remain fully supported.

WayKit saves your notes, transcripts, and links, then helps an assistant turn them into source-backed methods it can apply again later. It keeps the original evidence, shows where a rule came from, and lets you inspect, reuse, update, or share the result.

That is different from asking an AI to summarize something once. A summary helps with one conversation. WayKit keeps the useful parts so a future conversation can use them on new work.

[![Tests](https://github.com/tyreamer/waykit/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/waykit/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/waykit?color=38bdf8)](https://pypi.org/project/waykit/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/waykit/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399)](https://github.com/tyreamer/waykit/blob/main/LICENSE)

Works locally with Claude Code, OpenAI Codex, Claude Desktop, and Cursor.

---

## What WayKit does

When you paste text or a video link into a chat with an AI, it is usually available only in that conversation. Some assistants offer memory, but it may be limited, selective, or unavailable when you need to reliably reuse a specific source.

WayKit saves your links, notes, and video transcripts into folders on your computer. When you ask your AI a question, it searches those saved files, writes an answer based on what you saved, and shows you the exact sentence and timestamp from the original source.

---

## From saved facts to reusable experience

WayKit is not a replacement for an AI's personal memory. Memory can retain small facts; a WayKit pack gives the AI explicit, task-ready context for a particular kind of work: your preferences, style, strategies, constraints, and source-backed procedures.

Say you ask AI to help plan a trip.

### 1D — Context

You tell it:

> “I like great restaurants, direct flights, nice hotels, and I hate overpacked itineraries.”

It uses that for this conversation. Then the context disappears.

### 2D — Saved memory

The AI remembers:

> “Prefers good restaurants, direct flights, and relaxed trips.”

Useful — but flat. It remembers a few facts about you.

### 3D — WayKit context pack

Instead, imagine carrying a reusable **Travel Planning Pack**—a playbook for planning, not a record of every trip you have taken:

```text
Travel Planning

FLIGHTS
- Prefer nonstop whenever reasonable
- Avoid very early departures
- Compare cash vs points
- Preferred airlines and airports
- Seat preferences
- When fares are usually worth booking

HOTELS
- Preferred brands and loyalty programs
- Walkability matters
- Quiet rooms > nightlife
- What makes an upgrade worth paying for
- How much to spend based on the trip

FOOD
- Favorite cuisines
- Restaurants worth planning around
- Avoid tourist traps
- Reservation strategy
- Price range
- Dietary preferences

ITINERARIES
- Don't overpack the day
- Cluster activities geographically
- Leave time to explore
- One major thing per day
- Prefer experiences over checklist sightseeing

BOOKING STRATEGY
- What to book first
- How far ahead to book
- When to wait
- When to use points
- When flexibility matters more than price

PLANNING APPROACH
- Balance comfort, cost, and time
- What trade-offs matter most
- How much structure is useful
- Common mistakes to avoid
- Decision rules when options are close

SOURCES + RULES
- Trusted travel sites
- Loyalty-program rules
- Booking methods
- Decision criteria
```

Now you can say:

> **“Plan me five days in Japan.”**

The AI does not need you to teach it how you travel again. It already has the playbook: a reusable context for making travel decisions in your style.

**1D remembers what you said.**

**2D remembers facts about you.**

**3D carries a context pack for the work you want to do.**

---

## How to set it up

### 1. Ask your assistant to set it up

If you use Claude Code or OpenAI Codex, paste this sentence into your chat:

> Set up WayKit for me: https://github.com/tyreamer/waykit

Your assistant will download WayKit and connect to it automatically. When it finishes, restart your assistant once so it can use its new tools.

### 2. See the value offline

Say this to your assistant:

> Try WayKit with its offline debugging starter.

WayKit creates a test collection from a small debugging lesson, reviews one plan, and then applies the same saved knowledge to a second plan. The output shows the input, the reusable checklist, and how many saved knowledge units were reused. This test runs on your computer without downloading anything or calling an external API.

### 3. Need a different setup?

WayKit is designed to be set up by your assistant (`waykit start` / `lectic start`). If you need a manual, self-hosted, or contributor setup, see the [installation guide](docs/INSTALLATION.md).

The command-line guide covers `lectic start` for beginning a collection, `lectic share-artifact` for exporting one, and `lectic refresh` plus `lectic diff` for updating sources and reviewing what changed.

---

## What you can give it

* A public web article or blog link (extracts clean text without external scrapers)
* A YouTube link, when English captions are available
* Notes and text files (`.txt`, `.md`)
* Timed transcripts (`.vtt`, `.srt`)
* Browser shortcuts (`.url`, `.webloc`)
* Several sources combined around one task

WayKit does not require you to turn everything into a special format before saving it. Capture first, then process material when you are ready to use it.

## What you get back

Depending on your goal, WayKit can produce a source-backed review, decision, plan, checklist, improvement, or other reusable method. Each result can retain:

* The source passages that support it
* The situations where the guidance applies
* Disagreements and limitations that remain unresolved
* The method an assistant can apply to new work
* The build and source history needed to inspect or update it

See the [example gallery](docs/EXAMPLES.md) for five complete journeys: learning from a tutorial, developer architecture review, student study, professional evidence comparison, and a personal debugging playbook.

## Share and maintain what you build

Ask your assistant to export a collection as a portable web page (`waykit share-artifact` / `lectic share-artifact`), refresh it after source material changes (`waykit refresh` / `lectic refresh`), or compare two revisions (`waykit diff` / `lectic diff`). It handles the underlying steps and tells you what changed.

> Export my Engineering Standards collection as a web page.

> Update my Engineering Standards collection with the latest source folder and show me what changed.

Earlier source revisions and builds remain available. WayKit reports file-level changes immediately, then your connected assistant prepares updated knowledge without fabricating semantic change counts.

## How to use it every day

### 1. Save files and links

You can tell your assistant:

> Save this video: https://www.youtube.com/watch?v=24JAM7BACtA

Your assistant saves the link to your Inbox folder. If you give the name of a collection, it puts the link into that collection.

You can also drag web links from Chrome, Edge, or Safari directly into the `Documents/WayKit Inbox` (or `Documents/Lectic Inbox`) folder on your computer. You can also drop text files (`.txt`, `.md`) and transcript files (`.vtt`, `.srt`) into that folder. WayKit does not need a background app running to notice these files. The next time you open your assistant, it will tell you what files are waiting in your folder and ask where you want to put them.

### 2. Ask questions about what you saved

You can ask your assistant to read your saved files and answer questions:

> What does my debugging video say about fixing parser bugs?

Your assistant reads your saved transcript, summarizes the advice, and quotes the exact sentence and timestamp:

> According to Ada in debugging-lesson.vtt at 00:09, "Change one suspected cause at a time, rerun the same input, and compare the result."

You can also ask your assistant to extract [words and phrasing](docs/LANGUAGE-PATTERNS.md) from saved material:

> Extract the vocabulary and recurring phrases in this interview. Show examples and keep each speaker's wording separate.

The assistant preserves these observations with source passages and situation limits so you can reuse them in later writing tasks.

### 3. Share collections with coworkers

Ask your assistant to package a collection into a single `.waykit` (or `.lectic`) file for a coworker:

> Package my Engineering Standards collection so I can send it to my team.

When your coworker gives that file to their assistant, it can install the collection and search and quote the same material. When you update the pack, they can ask their assistant to update theirs.

---

## Supported files

| File type | What WayKit does with it |
| --- | --- |
| **Web articles & blogs** | Ingests clean, readable article text directly from public web pages using semantic HTML parsing without external dependencies. |
| **YouTube links** | Saves the link and downloads English captions automatically if they are available. |
| **Notes and text files (.txt, .md)** | Saves the text and splits it into searchable sections. |
| **Video and audio transcripts (.vtt, .srt)** | Saves the text along with timestamps so your AI can quote exact minutes and seconds. |
| **Browser links (.url, .webloc)** | Reads the web address when you drag a tab from your browser into your WayKit folder. |

Walled gardens and social networks (such as Instagram, TikTok, Facebook, and X/Twitter) are saved as links for reference without scraping.

---

## Checking your files

Ask your assistant to check whether every quote in a collection still matches the original source text:

> Verify the quotes in my Engineering Standards collection.

It tells you whether the quotes still match, or which source needs attention.

---

## Where your files are kept

All of your saved files, notes, and collections are stored in a folder called `.waykit` (or `.lectic`) in your user directory (for example, `C:\Users\YourName\.waykit` on Windows or `/Users/yourname/.waykit` on macOS). WayKit does not send your files to a cloud server. Your data stays on your computer.

For hosted access across your phone and web chat assistants (ChatGPT, Claude, Gemini), see [Reach your knowledge from anywhere](docs/CLOUD.md) (`waykit share` and `waykit cloud`).

---

## Contributing and license

WayKit is open-source software licensed under the MIT license.

For technical details, read the [developer documentation](docs/DEVELOPING.md), the [architecture notes](DESIGN.md), and the [tool reference](docs/MCP.md).
