# Capture Inbox contract

Capture records enter before expertise compilation. The source, the user's reason for saving it and the compiled method remain separate. Saving a URL does not mean we possess its content. The [iPhone Shortcut design](iphone-shortcut.md) is the first adapter; the core accepts the same folder records from any producer.

## Storage and identity

```text
SYNCED_INBOX/
  DATE.capture.json            # minimal v1 input: original_value + captured_at
  capture-UUID.json             # immutable event; write after its files
  capture-UUID/original.ext     # optional supplied attachment
  annotation-UUID.note.json     # optional personal context, after capture

LECTIC_HOME/                  # ~/.lectic, or a project's existing .expertise-compiler/
  blobs/SHA256                # one payload per exact byte hash, shared by everything
  capture/
    records/capture-ID.json     # original validated envelope
    state/capture-ID.json       # memberships, processing state, source IDs
    annotations/annotation-ID.json
    retrievals/HASH.json        # immutable linked acquisition receipts
    sources/SOURCE_ID/          # canonical normalized source run
  collections/COLLECTION_ID/  # normal source/IR/build history
```

Records use `capture.schema.json`; note events use `capture-annotation.schema.json`; local state uses `capture-state.schema.json`. All start at schema version `1.0`. No changes to existing source/knowledge schemas are required.

Required capture fields are `schema_version`, stable `capture_id`, timezone-aware ISO `captured_at`, `original_value`, `source_type`, `capture_status: captured`, `processing_status: pending`, and `provenance {adapter, origin}`. Optional fields are `url`, `shared_text`, actually known `title`, `user_note`, `requested_collections`, and `attachments`. A file reference has a relative `path` plus original `filename`; optional `sha256` and `byte_size` allow stronger arrival checks. The source type describes supplied input (`url`, `text`, `image`, `video`, `file`, `unknown`), not a claim of understanding its content. Known platform can remain in the original URL; no platform taxonomy is required in IR.

The incoming envelope always describes the capture moment. Desktop processing state is stored separately and must not be written back into that immutable envelope. The same ID and envelope can be imported repeatedly. Changing an existing ID is rejected. Separate intentional saves get separate capture IDs and notes; identical supplied content with matching URL/title/suffix shares a canonical source. Raw bytes deduplicate by hash even when source metadata differs. Capture URLs are never rewritten. For supported linked acquisition, a separate canonical identity permits cache reuse across URL variants while each capture retains its exact original link.

The importer reads top-level `.json` records, handles captures before `.note.json` annotation events, and ignores temporary non-JSON files. It reports malformed or unavailable files individually. Missing attachments can arrive on a later import; previously accepted bytes cannot be silently replaced. Unsafe paths and hash/size mismatches are rejected. Producers should save attachments before the JSON marker; without a supplied size/hash, V1 cannot independently prove an attachment finished syncing before its first readable arrival.

## Minimal share-input adapter

New phone setups use four actions and a `.capture.json` file validated by `capture-input.schema.json`. Only `original_value` and timezone-aware `captured_at` are required. Optional `user_note` and `requested_collections` retain the existing context boundary. The suffix identifies this v1 adapter contract; future incompatible input versions need an explicit new discriminator. Existing canonical JSON remains supported, including canonical envelopes with this suffix.

`scripts/capture_input.py` expands this transport input into the unchanged canonical capture schema. The desktop generates a deterministic ID from adapter version, normalized timestamp and exact shared text, identifies the first supplied HTTP(S) link, classifies URL-only versus text, and adds status/provenance. All shared text remains intact. Titles, endorsements and unavailable content are never inferred. Adapter provenance records `share-input-v1` / `supplied-value`; it does not claim that an unauthenticated file proves which app/device produced it.

No filename, import date, file modification time or collection name participates in capture identity. Copying/renaming/reimporting the same input is idempotent. A later capture time gives a separate event; identical text with an identical timestamp collapses into one. For separate same-time/same-value captures, use explicit IDs in canonical envelopes. Changing initial context on an already imported identity is rejected; append a note event instead. Changing time or shared content describes a new event, and never overwrites the old one. Renamed files must keep the `.capture.json` suffix.

The phone must still supply the original capture time and serialize a complete JSON object. The importer cannot reconstruct capture time from a delayed sync, and rejects missing/invalid timezone information. Import only downloaded files. Truncated JSON is rejected and can be retried; a syntactically valid but incomplete producer payload cannot be detected without a producer-supplied integrity manifest. The adapter does not ingest arbitrary loose text files.

## Membership and personal context

Absent a requested collection, the item belongs to Inbox. Memberships use existing stable collection IDs, not folders named after users' labels. Add keeps previous memberships; move replaces them; remove removes only the named memberships. Removing the final membership returns the capture to Inbox. Several captures can refer to one canonical source; it remains in a collection while any of those captures belongs there. Source snapshot changes never delete prior builds or originals.

An annotation event records its own ID and timestamp, the capture ID, optional note text and collections to add. Repeating the event is idempotent. Later notes append rather than rewriting history. Notes are unstructured personal context in this pass; they are not an automatic source-authority or policy engine. The assistant must interpret qualifications when doing the user's work, and tests cannot prove every natural-language qualification will be followed.

New build briefs automatically snapshot the collection's capture summaries, notes, unavailable-content flags and source links. Existing builds retain their own earlier context. Notes are never normalized into source segments, and attempts to cite note text as source evidence fail existing quote validation. Changing a note does not automatically reinterpret IR or rebuild every asset.

## State claims

| Processing status | What it means |
| --- | --- |
| pending | Saved; no eligible content has been normalized yet |
| awaiting_retrieval | A linked source is saved, but its content is unavailable |
| partially_processed | Available supplied/retrieved content is normalized, or only part of a linked item is available; extraction/reconciliation may still be needed |
| processed | Available supplied/retrieved content has a validated saved IR representation, including one available in historical revisions |
| needs_attention | Retrieval failed, an attachment is missing/changed/corrupt, a format lacks a processing adapter, or local normalization failed |

Every successful capture remains `capture_status: captured`, including items whose processing needs attention. A URL plus a processed excerpt remains partial unless the linked source was also retrieved and represented in validated IR. No status means the source is true, endorsed, company policy or exhaustively understood. Failed JSON import is reported at file level because no valid capture record can be accepted yet.

An optional `retrieval` object in local state records adapter/version, original/canonical URL, attempt/retrieval times, status, normalized source IDs and error. Missing means unattempted; `unavailable` means attempted but failed; `retrieved` means bytes acquired, with source IDs identifying successful normalization. Saved IR coverage is checked separately. Old `1.0` state records remain valid. [Full acquisition contract](YOUTUBE.md).

## Processing and reuse

`process` normalizes actually supplied text and `.txt/.md/.vtt/.srt` attachments, retrieves supported YouTube captions through a generic linked-source resolver, then enters the existing preparation coordinator. The assistant supplies semantic extraction and reconciliation. YouTube requires optional local yt-dlp; English captions are preferred manual then automatic, never video/audio. Successful acquisitions are hash-verified and reused across sessions and collections. Failed items retain their errors without blocking other URLs; retry processing after resolving the issue. Unsupported links and attachment bytes stay intact with a gap reported; there is no OCR, PDF parsing, audio/video transcription, article fetching or broad social scraping.

Canonical raw bytes live once in the home's blob store; collection snapshots receive them by hard link where the filesystem allows it and by copy otherwise, and are hash-verified either way. Keep the compiler project outside the synced intake folder. Blobs written by earlier project-local installs under `capture/blobs/` remain readable.

Repeated processing reuses matching sources and existing IR. A source-local extraction checkpoint can also be reused across collections or after a move when a historical validated IR and reconciliation receipt match, its source document is identical, and its unit IDs/relations are safe in the destination. Cross-source synthesis is not copied blindly; reconciliation is still needed. No model service is invoked by the Python utilities. Linked acquisition contacts YouTube only during requested processing; no background compilation runs when sync receives a file.

## Assistant-operated commands

```text
python scripts/ec.py capture --project PROJECT --action import --inbox SYNCED_INBOX
python scripts/ec.py capture --project PROJECT --action list --collection Inbox
python scripts/ec.py capture --project PROJECT --action show --item CAPTURE_ID
python scripts/ec.py capture --project PROJECT --action add --item CAPTURE_ID --to "AI Architecture" --to Security
python scripts/ec.py capture --project PROJECT --action move --item FIRST_ID --item SECOND_ID --to "Dinner Ideas"
python scripts/ec.py capture --project PROJECT --action remove --item CAPTURE_ID --to Security
python scripts/ec.py capture --project PROJECT --action note --item CAPTURE_ID --note "Do not treat as company policy"
python scripts/ec.py capture --project PROJECT --action process --collection "AI Architecture"
python scripts/ec.py capture --project PROJECT --action trace --build SAVED_BUILD
```

The assistant translates ordinary requests into these operations and keeps IDs internal. Query supports lexical terms in original shared text, titles and notes; `--since` is inclusive and `--until` exclusive, both ISO timestamps with timezones. Compute “this week” using the user's timezone. This is not semantic search over unacquired pages.

The intake directory can be imported again on demand. There is no automatic watcher, desktop-state sync back to the phone, shared account or multi-desktop merge; every project on one machine shares the same home. Local capture mutations invoked through the CLI use an OS writer lock; other legacy compiler commands should still be run serially in a project.

## Acceptance and remaining work

`fixtures/capture/workflows.json` supplies dinner and architecture cases to the same generic pipeline. Tests preserve notes, keep missing amounts and unretrieved links visible, trace multiple sources into outcomes, retain old assets after additions, and reuse source-local extraction. Their extraction and result prose are authored fixtures, not an independent semantic benchmark. Media tests preserve opaque bytes without pretending to decode them.

Live phone action availability, the four-action setup, variable date formatting, JSON serialization, actual Share Sheet payloads, iCloud delivery, large attachments and real assistant interpretation remain to be tested. Future adapters may acquire supported pages or transcripts; those acquisition records will need their own provenance. Relationships already use explicit IDs suitable for traversal. A graph database, dependency-driven rebuild service and bidirectional synchronization are future options, not part of this proof.
