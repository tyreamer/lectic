# Capture first; compile when useful

Use for saving a shared link/text/file, importing a synced Inbox, finding saved items, adding notes, moving memberships, processing pending captures or tracing a saved result. You operate scripts; users should not see internal IDs unless requested. The core contract is independent of iCloud and the phone adapter.

Apply the execution-environment check at the top of SKILL.md before saving/importing or processing. Check command-network access and yt-dlp before new YouTube retrieval, not on capture-only saves or cached reuse. If the host cannot execute the requested operation, preserve the request for a capable environment and explain what is not yet saved or processed; never simulate successful capture in chat.

Resolve PROJECT and SKILL_ROOT as usual. Don't guess the synced Inbox location or silently import an entire personal drive. Use a folder the user identifies, or locate a previously specified folder. The iPhone setup is [documented here](../docs/iphone-shortcut.md). If no phone Shortcut exists, explain that the proof requires one-time four-action manual assembly; do not claim it has been installed.

## Save and manage

Use `ec.py capture --project PROJECT --action import --inbox FOLDER` to import available canonical envelopes or minimal `.capture.json` inputs. The minimal adapter generates metadata on desktop; it still requires actual shared text and a timezone-aware capture timestamp. Do not substitute import time or file modification time. Existing full captures remain supported. Import is cheap storage only. Retry safely after sync; report per-file issues without making valid captures fail. Do not delete remote/synced files. Local project state is authoritative for subsequent processing; no background service or bidirectional state sync exists.

For directly supplied text/URLs/files, use `scripts/capture_write.py --inbox PROJECT/.expertise-compiler/capture-drop` with `--url`, `--text-file`, `--file`, `--note`, `--collection` and `--title` only when actually supplied, then import that folder. Preserve exact text in a UTF-8 file before passing it; do not interpolate arbitrary user text into shell commands. Set an honest origin. Never create a transcript or infer a recipe from a URL. Saving alone does not authorize extraction or a Capability Map.

For a pasted batch of links, create one capture per exact URL, including timestamp/query parameters. Save the accompanying reason as a personal note on each capture, never as `shared_text` or source evidence. Use a supplied collection name or infer a readable name from the stated purpose (for example, Entrepreneurship Growth); state that choice briefly without forcing a naming question. Do not invent video titles or endorse promises in the user's description. Reuse the recorded captures when continuing instead of saving the same batch again.

“Save these for later” stops after import. “Process this collection” or “Use these links to help me become an entrepreneur” authorizes deferred retrieval and preparation now, followed by the requested work. “I am going to use these later” alone is context, not authorization to process. A bare content-analysis request can follow discovery once processing is appropriate. No domain-specific routing is needed.

Natural interactions map to the following operations, inferred from meaning rather than domain keywords:

| User intent | Internal action |
| --- | --- |
| What's in my Inbox? | `capture --action list --collection Inbox` |
| Add this to Dinner Ideas | Save a new capture with that requested collection, or `--action add --item ID --to NAME` for an existing item |
| This belongs in AI Architecture and Security | `--action add --item ID --to NAME --to OTHER` |
| Put these three items in Dinner Ideas / move this talk | `--action move` with repeated `--item` and the destination |
| Remove from Dinner Ideas but keep in AI Architecture | `--action remove --item ID --to Dinner Ideas`; check remaining membership |
| Why did I save this? | `--action show --item ID`; quote the saved personal note, or say no reason was recorded |
| Saved this week about agent architecture | `--action list --query "agent architecture" --since ISO --until ISO`; derive the calendar interval in the user's timezone |
| Add or qualify my note | `--action note --item ID --note TEXT`; notes are append-only personal context |
| Which saved sources influenced this result? | `--action trace --build BUILD_PATH`; explain cited sources and separately show frozen build context |

Search is lexical over captured text, known titles and notes, not semantic search over unavailable webpages. Match a shown item by its ID internally; names/URLs may be ambiguous. Ask only to resolve actual ambiguity, never require users to manage IDs. Removing the last membership returns the item to Inbox. Membership does not mean endorsement, authority or permission to use all aspects of a source.

## Process and use later

“Process the unprocessed items in NAME” uses `capture --action process --collection NAME`. It normalizes supplied text/eligible attachments and retrieves supported YouTube captions through the linked-source resolver. It links canonical sources into collection snapshots, reuses eligible verified extraction, then returns the ordinary prepare/extract/reconcile task. Continue with `ec.py work --collection NAME --action prepare`, passing `--reconciled` only after actual review. Continue into the user's original goal or requested discovery after preparation; do not stop at downloaded captions. No method or asset is built by preparation alone.

YouTube processing prefers manual English captions, otherwise automatic English captions, using local `yt-dlp`. It acquires the full available caption track even for timestamp links, never video/audio or speech-to-text. Do not ask the user to export/download transcripts. If `yt-dlp` is missing, explain that the links are saved and ask for authorization to install the optional executable; never install it implicitly. If access or captions fail, retain the unavailable items, explain the specific gap and use successful sources. Retry processing after resolving the issue; successful acquisitions are reused, and no new capture is needed. Titles/descriptions are not fallback transcripts. Inspect returned `retrieval_state` when explaining what succeeded. [Adapter details](../docs/YOUTUBE.md).

When a goal or discovery request references a capture-fed collection, process its available pending material first, then use the existing goal or map flow. Never silently omit URL-only items: show what remains unavailable and how that limits the goal. Don't demand complete retrieval of every item before using adequate available material. “Plan five dinners” does not license invented quantities; “review architecture” does not make a saved opinion company policy. These are examples of the same source/context boundary, not special domain rules.

Notes and retrieval gaps are automatically snapshotted into new build briefs as private context. Read that context when applying a method. Treat it separately from source evidence and from compiler inference. It may constrain this user's outcome, but do not turn a note into an expertise unit or cite it as source testimony. A note saying “I like only the sauce” or “not company policy” qualifies intended use without editing the original source. Revised notes affect a future brief, not immutable earlier assets. Clearly label any general suggestions beyond supplied material.

Respond with accurate states: captured means saved; awaiting retrieval means linked content has not been acquired; partially processed means available content was normalized but knowledge preparation or linked content remains; processed means the available supplied/retrieved content has a validated saved IR representation (not that its claims are true); needs attention includes failed retrieval, missing/corrupt attachments or unsupported file processing. Downloaded captions alone never mean processed. A URL plus an excerpt never proves the linked page/video was retrieved. Explain when a supplied excerpt can still help.

Do not run full compilation on every import, automatically rebuild every affected capability, or install a watcher. For a meaningful collection update, the user can request a fresh Capability Map or a new build; old assets remain intact.
