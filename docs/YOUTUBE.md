# YouTube links to reusable expertise

Paste YouTube links and explain why you are keeping them. Lectic saves each link and your personal context. When you ask it to process or use the collection, it retrieves available English captions, preserves their original bytes, and continues into normal evidence-linked extraction and reconciliation. No manual transcript export is required.

## Dependency and acquisition

Python remains standard-library-only. Linked YouTube retrieval additionally requires a current **`yt-dlp` executable on the assistant process's PATH**, with network access to YouTube. Lectic detects it and gives an actionable error if absent. It never installs software or downloads binaries automatically. Ask your assistant to install it if you want to authorize that setup; see [yt-dlp's official installation instructions](https://github.com/yt-dlp/yt-dlp#installation). Skill updates do not install or update yt-dlp.

The adapter invokes yt-dlp without a shell, reads video metadata, selects one caption track, then downloads only that track. Both commands use `--skip-download` and `--no-playlist`. User configuration, plugins and remote components are disabled so they cannot introduce media downloads or hidden behavior. No audio, video, speech-to-text, cookies/login setup, paid API or model call is used. Metadata and captions have size checks, and subprocesses have bounded retries and timeouts.

Selection prefers usable manual English captions (`en`, then English variants), followed by automatic English captions (`en-orig`, then `en`, then other English variants). VTT is preferred, with SRT accepted when available. Non-English-only videos are reported as unavailable. An English track may be a platform-generated translation; the adapter does not independently verify its language accuracy or translation origin. Automatic captions can contain errors, and transcripts do not capture visual-only evidence.

Supported URLs include watch, short `youtu.be`, mobile, shorts, embed and live-video links with a valid video ID. Additional query parameters are accepted. A watch link containing a playlist parameter processes **only that video**. Playlist-only links are rejected with guidance to supply individual video links; the adapter never expands a playlist.

## Saved data and provenance

```text
capture/import (no retrieval)
  → explicit collection processing
  → generic linked-source resolver
  → YouTube caption adapter / verified acquisition cache
  → original bytes + canonical source segments
  → existing extraction / reconciliation / build workflow
```

`scripts/linked_sources.py` routes supported links and caches acquisitions independently of Expertise IR. `scripts/ingestors/youtube.py` supplies ordinary `TranscriptInput` records. No source or knowledge-unit schema change is needed. Title and creator/channel come from retrieved metadata; missing values stay unknown. A title or description is never a substitute for captions.

The immutable capture retains the **exact originally shared URL**, including `&t=868s`. Retrieval uses a separate canonical video URL and always acquires the full available caption track; the timestamp never crops it. Source metadata retains the original URL from the first acquisition. Later captures of other URL variants keep their own exact links while sharing the same cached source. Capture tracing therefore distinguishes the link someone shared from the transcript supporting a quotation.

Successful acquisition receipts live in `capture/retrievals/`, governed by `linked-retrieval.schema.json` version `1.0`. They record adapter/version, canonical URL, retrieval time, caption filenames, raw hashes and source metadata. Raw caption bytes share the capture blob store; checksums are verified on reuse. The cache key includes adapter/version and canonical URL. Repeated processing, interrupted normalization, fresh sessions and collection memberships reuse those bytes without redownloading them. There is no automatic freshness check or user-facing caption refresh operation yet; a later YouTube edit does not silently rewrite saved evidence.

Capture state gains an optional `retrieval` field under its existing backward-compatible `1.0` schema: adapter/version, original/canonical URLs, attempt/retrieval times, status (`unavailable` or `retrieved`), normalized source IDs and error. Old records remain valid. Personal context stays in captures/annotations and private build briefs, never in transcript segments or source-derived knowledge.

## States and failure handling

| Stage | User-visible claim |
| --- | --- |
| URL saved, no retrieval | Awaiting retrieval; the link is safely captured |
| Retrieval failed | Needs attention; the reason is retained and other items can proceed |
| Caption bytes acquired but invalid | Needs attention; retrieved bytes are not usable normalized evidence |
| Captions normalized | Partially processed; extraction/reconciliation still required |
| Validated saved IR covers the available source content | Processed; this does not certify truth or effectiveness |

Missing captions, unsupported languages, unavailable/private videos, access restrictions, rate limits, outdated yt-dlp and network failures can prevent acquisition. Retry collection processing after resolving the issue; unsuccessful acquisitions are not cached as successes. Successful items and old builds remain intact. Unsupported other platforms stay captured but unavailable, even if their accompanying text can be used. Malformed caption bytes remain inspectable; repeatedly processing the same cached invalid bytes does not repair them.

## Regression and live retest

`tests/test_youtube.py` mocks the executable/network boundary and includes the exact eight-link entrepreneurship journey in `fixtures/youtube/entrepreneurship.json`. It checks capture, retrieval, normalization, private context, authored extraction/reconciliation, a validated build, tracing, retries and fresh-session reuse. Mock captions are synthetic; no assertions about those real videos' contents or current accessibility follow from these tests.

For a live test, use one or two public captioned videos first, then the eight-link fixture. Ask:

> Use Lectic to save these YouTube links as Entrepreneurship Growth. My reason for saving them is personal growth and becoming an entrepreneur; that is my context, not evidence or a promise of income. Process the collection now, retrieve available captions yourself, and use the supported methods to propose a practical first-week experiment. Tell me which videos were actually retrieved and what remains unavailable. Preserve exact links, including timestamps, and save the result for reuse.

Append the actual links. If the optional dependency is missing, authorize its installation separately. Inspect actual caption files and evidence timestamps, then repeat the request in a fresh session in the same project. No second upload or successful-caption download should be necessary. Live YouTube access and assistant judgment must be assessed separately from deterministic tests.
