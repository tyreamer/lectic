<div align="center">

# Lectic

### Save what you trust. Your AI learns the playbook.

[![Tests](https://github.com/tyreamer/lectic/actions/workflows/tests.yml/badge.svg)](https://github.com/tyreamer/lectic/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lectic?color=38bdf8)](https://pypi.org/project/lectic/)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/tyreamer/lectic/blob/main/docs/DEVELOPING.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399)](https://github.com/tyreamer/lectic/blob/main/LICENSE)
[![Catalog](https://img.shields.io/badge/starter-shelf-38bdf8)](https://tyreamer.github.io/lectic/registry.html)

**[Quickstart](#quickstart-in-10-seconds)** · **[How it Works](#the-problem--the-solution)** · **[Daily Flow](#talk-naturally-to-your-ai)** · **[Key Benefits](#why-lectic)** · **[Sharing](#share-with-your-team)**

Works with **Claude Code** · **OpenAI Codex** · **ChatGPT** · **Claude Desktop** · **Cursor** · any AI assistant

</div>

---

### The Problem & The Solution

**Your AI has amnesia.**

You watch a brilliant 40-minute talk, study an expert teardown, or read a masterclass on engineering. You paste it into Claude or ChatGPT, get one great answer, and close the chat.

The next day, **the AI forgets everything**. You're back to re-pasting excerpts, re-prompting context, or settling for generic chatbot fluff.

**Lectic gives your AI a permanent memory playbook.**

Save talks, articles, and transcripts once. Lectic turns that material into reusable rules, checklists, and reviewer playbooks—with the author's exact quotes and timestamps attached.

Save it once; your AI applies those lessons across Claude, ChatGPT, Codex, and your team forever.

---

## Quickstart in 10 Seconds

### 1. Let your AI set it up for you (Zero-command install)
Paste this directly into **Claude Code** or **OpenAI Codex**:

> Set up Lectic for me: https://github.com/tyreamer/lectic

Your assistant handles installation and connection automatically. **Restart your assistant once** after setup.

### 2. Try the instant offline sample
Say to your assistant:

> Try Lectic with its offline debugging starter.

It immediately reviews a sample debugging plan and generates a reusable checklist using real expert procedures—**running 100% offline without API keys or downloads**.

Then try your own work:
> Use my Debugging Starter to review this plan: [paste your plan]

### 3. Or install via terminal in 30 seconds

```bash
pip install --upgrade lectic
lectic setup --yes
lectic try
```

Run `lectic status` anytime to see your saved playbooks and connected AIs.

---

## Talk Naturally to Your AI

Speak in plain English:

- **Save without friction:**
  > Save this video for later: https://www.youtube.com/watch?v=…
  
  *(Saves straight to your **Inbox**—no tagging required, no extra API fees.)*

- **Drag and Drop:**
  Drag browser tabs from Chrome, Edge, or Safari, or drop notes directly into your `Documents/Lectic Inbox` folder. No background servers running, zero battery drain. When you next chat with your AI, it surfaces what you dropped:
  > *"I noticed you dropped a link to an engineering talk into your Lectic folder. Would you like me to add it to your Architecture playbook?"*

- **Put playbooks to work:**
  > Use my Debugging playbook to review this code change.
  
  *(Your AI evaluates your work using the expert's rules and quotes the exact source timestamp.)*

- **Share with teammates:**
  > Share my Engineering Standards playbook with the team.
  
  *(Your assistant exports a single file and gives a 1-sentence prompt for your teammate: `"Install this Lectic pack: [link]"`.)*

**Want to use it in ChatGPT on the web or your phone?** Run `lectic share` to get a private link for ChatGPT or your iPhone ([cloud & phone guide](docs/CLOUD.md)).

---

## Why Lectic?

### 1. Drag-and-Drop Folder
No background servers or battery drain. Drag tabs from Chrome, Edge, or Safari (`.url`, `.webloc`), or drop text notes (`.txt`, `.md`) and transcripts (`.vtt`, `.srt`) straight into `Documents/Lectic Inbox`. Syncs effortlessly between phone and laptop via iCloud or OneDrive.

### 2. Shareable Playbooks (`.lectic`)
Export any collection into one clean file (`lectic pack "Engineering Standards"`). Your rules, checklists, and source quotes travel together in a neat, shareable bundle.

### 3. Exact Quotes Attached (Zero Guesswork)
Your AI shows where every piece of advice came from. Every rule is anchored to an exact quote and timestamp in the original transcript. Run `lectic verify` anytime to confirm that all citations are intact.

### 4. Verified Author Stamp
Playbooks are stamped with the author's name and verification key, guaranteeing that the playbook is authentic and hasn't been modified.

### 5. Team Standards in 1 Step
Compile team conventions once. New hires install them in seconds (`lectic install <url> --as engineering --pin`) and their AI immediately works inside the team's conventions across Claude and ChatGPT. Update in place anytime with `lectic update engineering`.

---

## Supported Inputs & Formats

| What you save | How Lectic handles it |
| --- | --- |
| **Notes & text snippets** | Saved immediately; organized when you're ready |
| **Transcripts (.txt, .md, .vtt, .srt)** | Parsed with timestamps so your AI can cite exact moments |
| **Browser drag-and-drop** | Drag tabs straight into your Lectic folder from Chrome, Edge, or Safari |
| **YouTube links** | Saved instantly; English captions downloaded automatically if available |
| **Claude Code, Codex, Cursor** | Connected automatically via open AI tools standard |
| **ChatGPT & Mobile** | Connect securely via private web link (`lectic share`) |

---

## Share with Your Team

Share playbooks with teammates, students, or friends:

```bash
# Set your author name
lectic identity set "Alex Rivera" --contact alex@platform.org

# Export a team playbook with full source material
lectic pack "Engineering Standards" --team --version 2.1.0

# Upload to your team's storage (GitHub, S3, or Google Drive)
lectic publish "Engineering Standards" --to https://github.com/org/repo
```

Your teammates install with one predictable command:
```bash
lectic install https://github.com/org/repo/releases/download/v2.1.0/standards.lectic --as standards --pin
```

When standards evolve, teammates update with one command:
```bash
lectic update standards
```

---

## Honest Boundaries

- **Exact Quotes, Not Magic:** Lectic confirms that every quote matches the original source text. That gives you clear proof of where advice came from, but your AI still needs your expertise and judgement.
- **Local & 100% Yours:** Your playbooks live on your own computer in `~/.lectic`. Back up with `lectic backup`, restore anywhere with `lectic restore`.
- **Open Source:** MIT licensed and actively developed. Feedback, feature requests, and PRs are warmly welcomed!

For contributors: [development guide](docs/DEVELOPING.md) · [architecture](DESIGN.md) · [tool reference](docs/MCP.md) · [MIT license](LICENSE).
