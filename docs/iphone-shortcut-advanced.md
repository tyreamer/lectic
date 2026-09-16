# Advanced iPhone capture: full records

For new setups, use the [four-action Shortcut](iphone-shortcut.md). This older recipe remains compatible and supports per-item loops, phone annotations and attachments.

Share something worth keeping, save it immediately, and decide what to do with it later. This adapter writes small capture records to a synced folder. It does not retrieve a linked page, transcribe a video, generate knowledge or rebuild capabilities.

This is an action-by-action Shortcut design plus tested local adapter files, **not an installable, signed `.shortcut` download**. The desktop contract has automated tests; these iPhone actions and cross-device iCloud delivery still need a real-device acceptance run. No native app or hosted backend is required.

## One-time folder setup

In Files, create `iCloud Drive/Expertise Compiler/Inbox`. On the desktop, enable iCloud Drive and locate the same folder. Use the path shown by your machine rather than assuming a fixed Windows path. Make the folder available offline so the importer can read actual files, not cloud placeholders. Keep the compiler project on a local filesystem, separate from this synced intake folder. [Apple: iCloud Drive on Windows](https://support.apple.com/guide/icloud-windows/icw0144825a5/icloud), [keep files downloaded](https://support.apple.com/en-gb/guide/icloud-windows/icw8531ad6b7/icloud).

The contract also works with a manually copied folder or another file-sync provider. iCloud is only this first adapter's transport. Its storage limits still apply; large media is optional.

## Build the basic Shortcut: save to Inbox without questions

Create a shortcut named **Expertise Compiler**. Enable **Show in Share Sheet** and accept **URLs** and **Text**. Set absent input to stop with “Share a link or text to save it.” Do not silently read the clipboard. Apple documents [Share Sheet activation](https://support.apple.com/en-mt/guide/shortcuts/apd163eb9f95/ios) and [input types](https://support.apple.com/en-lamr/guide/shortcuts/apd7644168e1/ios).

Add these actions in order. Action labels may vary with iOS language/version; the values and output contract below are authoritative.

1. **Repeat with Each** item in Shortcut Input. Each shared item gets its own capture ID and record; never append into one shared JSON file.
2. **Get Text from Input**, using Repeat Item. Save the result as `OriginalValue`. If empty, stop that capture without a success message.
3. Create a unique suffix using **Current Date** → **Format Date** with custom format `yyyyMMddHHmmssSSS`, plus two separate **Random Number** actions, each between `10000000` and `99999999`. If number-to-text conversion adds separators, use Replace Text with regex `[^0-9]` and an empty replacement on each number. A **Text** action combines `capture-`, the formatted date and both numbers separated by hyphens; save as `CaptureID`. For example: `capture-20260915120000123-12345678-87654321`. Generate it once per shared item and keep it unchanged through the save. The contract accepts UUIDs too, but this recipe does not require a UUID action or a third-party app. Collisions are rejected, never overwritten.
4. **Current Date** → **Format Date**, using ISO 8601 with a timezone. Save as `CapturedAt`. For a custom format use `yyyy-MM-dd'T'HH:mm:ssXXX`; verify the sample contains a timezone offset or `Z`.
5. **Get URLs from Input**, using Repeat Item. If any URLs were supplied, take the first as `OriginalURL`; otherwise use empty text. This extracts a supplied link; do not add Get Contents of URL, webpage extraction, AI actions or transcription. `OriginalValue` still retains all provided text if it contains multiple links.
6. Set `SourceType` to `text`. If `OriginalValue` is exactly `OriginalURL`, set it to `url`.
7. Add a **Dictionary** with the following keys. Use Magic Variables as values, not hand-built JSON string interpolation.

| Key | Type | Value |
| --- | --- | --- |
| schema_version | Text | `1.0` |
| capture_id | Text | CaptureID |
| captured_at | Text | CapturedAt |
| original_value | Text | OriginalValue |
| source_type | Text | SourceType |
| capture_status | Text | `captured` |
| processing_status | Text | `pending` |
| provenance | Dictionary | `adapter` = `iphone-shortcut`; `origin` = `share-sheet` |
| url | Text | OriginalURL, or empty text |
| shared_text | Text | OriginalValue |

8. Convert the Dictionary to JSON text with **Get Text from Input** using the Dictionary as input. During setup, use Quick Look once and verify it is a JSON object, including quotes escaped inside text. Dictionary serialization protects quotes, backslashes, emoji and newlines; don't paste user text between literal JSON quotation marks. [Apple: using dictionaries](https://support.apple.com/en-ie/guide/shortcuts/apd43b69f337/ios), [JSON in Shortcuts](https://support.apple.com/en-gb/guide/shortcuts/apd0f2e057df/ios).
9. **Set Name** to `CaptureID.json`, then **Save File** in the fixed `Expertise Compiler/Inbox` folder. Disable Ask Where to Save and disable overwrite. On first use, grant the folder access the Shortcut needs. Verify the saved filename actually ends in `.json`, not `.json.txt`. [Apple: file sharing actions](https://support.apple.com/en-au/guide/shortcuts/apdaf74d75a5/ios).
10. Only after Save File succeeds, show **“Saved to Inbox. Content has not been retrieved or processed.”** End Repeat.

The runtime path is Share → Expertise Compiler → saved. There is no collection picker or note prompt in the basic version. A social app may supply only a link; that is still a successful capture. If an app does not expose matching share data, this shortcut may not appear; manually sharing its copied link is a fallback, not evidence that its media was acquired.

Compare your first output with [the valid URL envelope](../fixtures/capture/shortcut-url.json). It is a synthetic example, not an actual saved link.

## Optional context, after the item is already safe

Duplicate the Shortcut as **Expertise Compiler with Context** if desired. After step 9, add a menu with **Done** first, then **Add context**. Canceling or selecting Done leaves the original capture saved in Inbox.

Under Add context, optionally ask for a collection. A static list of your recent collections, Inbox and Other is sufficient; Other asks for a name. The adapter does not fetch a live collection list. Build an `AddCollections` List containing the selected name; use `Inbox` when no other destination is chosen. Then Ask for Input: **“Why are you saving this? Leave blank to skip.”** A canceled dialog stops this optional branch without losing the original capture.

Generate a fresh date-and-random suffix using the same steps, prefixed with `annotation-`, and a new ISO timestamp. Use a Dictionary with:

| Key | Type | Value |
| --- | --- | --- |
| schema_version | Text | `1.0` |
| annotation_id | Text | New unique ID with annotation prefix |
| capture_id | Text | Original CaptureID |
| annotated_at | Text | New ISO timestamp |
| user_note | Text | Optional input; empty is valid |
| add_collections | Array | AddCollections |

Serialize and save as `AnnotationID.note.json` in the same folder. Do not rewrite the original capture. These optional events add memberships; they do not remove Inbox membership automatically. Later, “Move this to Dinner Ideas” can remove Inbox membership explicitly. See [annotation example](../fixtures/capture/shortcut-annotation.note.json).

The importer handles the capture before its annotation. If sync delivers the annotation first, it reports a pending parent and retries on the next import. The note means “my reason for saving,” never “this source is policy” or “I endorse all of it.”

## Attachments: optional extension, not part of the first phone acceptance test

The generic contract and desktop writer preserve arbitrary supplied file bytes, including images and videos. The basic Shortcut above deliberately accepts URL/text inputs only. To extend it, accept file/media inputs, save each original file in `Inbox/CaptureID/` first, then include `attachments` in the record as a List of Dictionaries with relative `path` and `filename`. If available, include `byte_size` or SHA-256 to detect incomplete delivery. Save the JSON record last. Do not convert an image or video to text and claim that its content was captured.

Example attachment reference: `{"path":"capture-UUID/photo.jpg","filename":"photo.jpg"}`. Keep references inside Inbox. The importer preserves bytes, retries missing attachments, and rejects traversal or changed hashes. Only `.txt`, `.md`, `.vtt` and `.srt` attachments are normalized today. Images, videos, PDFs and other files remain saved with a needs-attention explanation; there is no OCR, transcription or document parser. This extended phone branch has not been device-tested.

## Desktop handoff

Tell the assistant, using your actual synced folder path:

> Import new captures from my synced Expertise Compiler Inbox at [folder path]. Show me what's saved and what still needs content. Don't compile anything yet.

It runs the importer, which copies immutable records and content-addressed attachments into the local project's `.expertise-compiler/capture/`. Repeating import is safe. Sync files are never deleted or marked processed by the importer. Processing state, memberships and later local notes belong to this project; this proof does not sync desktop state back to the phone or combine separate desktop projects.

Later say “Move this to Dinner Ideas,” “Put this in AI Architecture and Security,” or “Process the unprocessed items in Dinner Ideas.” Processing normalizes only actually supplied text and hands extraction to your existing assistant when requested. URL-only items remain unavailable; add exported text as a new capture if you want to use their contents today. No background watcher runs.

For local development, the assistant can use the reference producer and importer:

```text
python scripts/capture_write.py --inbox "SYNCED_FOLDER" --url "https://example.com/a-talk" --note "Interesting, not policy"
python scripts/ec.py capture --project "LOCAL_PROJECT" --action import --inbox "SYNCED_FOLDER"
python scripts/ec.py capture --project "LOCAL_PROJECT" --action list --collection Inbox
```

## Exact first live test from your iPhone

1. In Safari, share a page → **Expertise Compiler**. Confirm “Saved to Inbox”; check that one `.json` file appears in Files. Do not expect the webpage body or a video transcript.
2. In Notes, select and share this text: **“For two servings, cook 200 g dry pasta according to its packet. Warm 250 g tomato sauce and mix with the cooked pasta.”** Use the same Shortcut. Optionally use the context variant with **“Good for a quick weeknight meal.”**
3. Wait until the desktop's synced files are downloaded. Ask the assistant to import, show Inbox, then import again. Expect two captures, no duplicate records, and no expertise compilation yet. The URL should say awaiting retrieval.
4. Say: **“Move those two items to Dinner Ideas. Process the usable material, then plan one dinner for two and list what I need to buy. Flag anything the saved link doesn't establish.”** Expect a plan grounded in the actual pasta text, a separate personal note, and an explicit unavailable-link warning.
5. Open a fresh assistant session in the same local project: **“What's in Dinner Ideas, and why did I save these items?”** No re-upload should be needed. Add a second membership, then remove only one: **“Put the pasta item in Quick Meals too. Remove it from Dinner Ideas but keep it in Quick Meals.”**

Record app/iOS version, whether Save File and JSON serialization worked, sync delay, import result and any manual help. Automated desktop tests cannot establish Share Sheet availability or iCloud delivery reliability.
