# iPhone capture: four actions

Save a link or selected text to Inbox. The **desktop generates the metadata**; your phone only sends what you shared and when you saved it.

**If your Lectic has a link** (`lectic share`, or an always-on server), the two-action Shortcut in [Anywhere](CLOUD.md#your-phone) posts captures straight to it and needs no synced folder. This page is the folder-based alternative.

This is a simpler manual setup, **not an installable Shortcut link yet**. The importer is tested; the action configuration and actual iCloud delivery still need testing on an iPhone. A prebuilt, device-tested iCloud Shortcut link remains the next distribution step.

Existing shortcuts and an `Expertise Compiler/Inbox` folder still work. Keep importing your existing folder; you do not need to move saved captures or recreate a working Shortcut for the rebrand. New setups below use Lectic.

## Set up once

In Files, create **iCloud Drive → Lectic → Inbox**. Enable iCloud Drive on your desktop and make that folder available offline. Keep your compiler project outside this synced folder. [Apple's Windows setup](https://support.apple.com/guide/icloud-windows/icw0144825a5/icloud).

In Shortcuts, create **Lectic**. Enable **Show in Share Sheet**, accepting **URLs** and **Text**. Set absent input to stop. This basic version is for one shared link or selected text at a time; don't enable images/video/files and convert them to text.

Add these **four actions**. Blue variable tokens are selected from the variable picker, not typed as literal words. Apple supports [formatting dates inside variables](https://support.apple.com/en-jo/guide/shortcuts/apd71b0ac246/ios) and [custom date formats](https://support.apple.com/en-in/guide/shortcuts/apd8d9b19184/ios).

### 1. Dictionary — two entries

| Key | Type | Value |
| --- | --- | --- |
| `original_value` | Text | **Shortcut Input** variable |
| `captured_at` | Text | **Current Date** variable, formatted as **ISO 8601** |

Tap the Current Date token to set its date format. The output must contain a timezone, for example `2026-09-15T12:00:00-04:00`. Do not type a fixed example date.

No capture ID, URL-detection logic, status, source type or provenance fields are needed. Do not build JSON by pasting the shared text between quotation marks: the Dictionary handles escaping.

### 2. Get Text from Input

Input: the **Dictionary** from action 1. This serializes it as JSON. During setup, temporarily use Quick Look to check the two keys and timestamp, then remove Quick Look.

### 3. Set Name

Input: **Text** from action 2.

Name: **Current Date** variable followed by the literal `.capture.json`.

Set this date token's format to **Custom**: `yyyyMMdd-HHmmssSSS`. Example filename: `20260915-120000123.capture.json`. The filename only prevents file collisions; the desktop reads capture time from the record, not the filename or sync modification time. Keep the `.capture.json` suffix.

### 4. Save File

Input: the **Renamed Item** from action 3.

- Destination: **iCloud Drive/Lectic/Inbox**.
- **Ask Where to Save: off**.
- **Overwrite If File Exists: off**.

Allow folder access on first use. Check that the filename ends in `.capture.json`, not `.json.txt`. If saving fails or asks about a name collision, retry with a new filename; never replace an earlier capture. An optional fifth action can show **Saved to Inbox** after Save File succeeds.

That's the entire basic Shortcut. No collection or note questions are necessary. [Apple: enabling the Share Sheet](https://support.apple.com/en-mt/guide/shortcuts/apd163eb9f95/ios), [Dictionary and JSON handling](https://support.apple.com/en-gb/guide/shortcuts/apd0f2e057df/ios).

## What the desktop handles

The importer expands the two fields into the existing canonical capture format: stable ID, source type, supplied URL detection, provenance, pending status and Inbox membership. It validates the timestamp and preserves the full shared value, including quotes, emoji and newlines. Importing again, renaming the file or changing sync folders does not duplicate a capture.

Only supplied HTTP(S) links are detected; capture/import retrieves no page or media content. A URL alone stays **awaiting retrieval** until requested processing. The desktop can then retrieve [YouTube English captions](YOUTUBE.md) using optional yt-dlp; other linked platforms remain unavailable. Text alongside a URL remains available as an excerpt, without implying that the linked content was acquired.

Capture IDs derive from the capture time and exact shared value. Two identical shares with the exact same timestamp collapse into one capture; a later save gets a separate capture. Matching source content can still share one normalized source. This lightweight format does not support distinct same-time/same-content events; use the advanced format with explicit IDs if that matters.

## Import and add context later

Use the actual downloaded folder on your desktop:

> Import captures from [my synced Lectic Inbox path]. Show what's saved and what still needs content. Don't compile anything yet.

Then, when useful:

> Put that talk in AI Architecture and Security. Add this note: “Interesting perspective, but don't treat it as company policy.”

Notes stay separate from sources. Importing performs no extraction or compilation, and never deletes or changes synced files. Local membership and processing state are not synced back to the phone. [Full storage contract](CAPTURE.md).

Optional phone context can be added later using a separate Shortcut variant: the minimal input also accepts `user_note` (Text) and `requested_collections` (Array of names). These fields are immutable initial context; later edits should use desktop annotations. Keep the basic save free of prompts.

<a id="exact-first-live-test-from-your-iphone"></a>

## Exact first live test

1. In Safari, share a page → **Lectic**. In Files, confirm one `.capture.json` file exists with the actual URL and timezone-aware capture time.
2. From Notes, select and share: **For two servings, cook 200 g dry pasta and mix with 250 g tomato sauce.** Confirm a second file exists.
3. Wait for desktop download. Ask the assistant to import twice. Expect **two captures, no duplicates, no compilation**. The URL should say awaiting retrieval.
4. Say: **“Move the pasta text to Dinner Ideas. Add the note 'Good for a weeknight.' Process its supplied text, then plan one dinner for two and list the ingredients. Do not infer anything from the saved URL.”**
5. Open a new session in the same project. Ask **“What's in Dinner Ideas, and why did I save it?”** No re-upload should be needed.

Record iOS/app versions, setup time, manual help, filename/JSON output and sync delay. Desktop tests do not establish real-phone usability. Compare setup effort with the previous recipe before inviting more testers.

## Already using the earlier Shortcut?

Keep using it. Full `.json` capture records and `.note.json` annotation events still import unchanged. Both formats can coexist in the same Inbox. The [advanced recipe](iphone-shortcut-advanced.md) retains per-item loops, explicit IDs, phone annotation events and optional attachment instructions.

The minimal sample is [simple-url.capture.json](../fixtures/capture/simple-url.capture.json). Older installed compiler copies need updating before they can import it; use the checkout or follow the [installation update guidance](INSTALLATION.md).
