# Lectic invited pilot

The pilot turns sources into a reusable pack, creates useful work inside Lectic, and shares a fixed pack version so someone else can create something different. This branch is a **local implementation under review**, not a launched cloud service.

The owner explicitly chose to keep it local on September 26, 2026 and will provide separate cloud accounts. No Supabase or Render resources were created or changed.

## What is implemented

| Area | Behavior |
|---|---|
| Web app | Responsive React/TypeScript library, three starter cards, preserved pack selection through OAuth, six creation choices, source disclosures, copy and Markdown download. |
| Sources | URL/text capture and bounded uploads, Inbox by default, Saved / Processing / Ready / Needs content states, screenshot/video fallback. |
| Compiler | Exact-quote extraction, cross-source reconciliation, coverage assessment, reusable methods, validated outcomes, separate assistant semantic review. |
| Media | PDF text and page OCR, image interpretation, timestamped Whisper transcription, up to 12 sampled video frames. Originals remain private. |
| Jobs | Durable SQL records, priorities, account leases, fixed-home subprocesses, heartbeats, cancellation, three job attempts, checkpoints. |
| Spending | Atomic reservation before each paid request, actual usage reconciliation, account-scoped cache. Uncertain requests keep their reservation and require operator reconciliation. |
| Sharing | Unlisted fixed snapshots, public pack preview, invited recipient copy, immediate revocation, private `.lectic` downloads. Existing recipient copies survive revocation. |
| Storage | Separate homes and assets by validated account UUID, private Supabase originals/backups when deployed, automatic compiler-home backups after committed pack/result operations. |
| Authentication | Google/Apple OAuth via Supabase; server validates user, active session and invitation. Production fails closed without dedicated configuration. |
| Mobile | Swift app + Share Extension with shared Keychain/container and background URLSession uploads; Kotlin share intents + encrypted session storage + WorkManager retries. |

The marketing page remains a separate static site. Its visual demo remains an authored example; it does not pretend to perform live generation.

## Local review

Use Python 3.10+ and Node 24 for development. Pilot users will not need either.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r cloud/requirements.lock
.venv/Scripts/python -m pip install --no-deps -e .
cd apps/web
npm ci
npm run build
cd ../..
$env:LECTIC_DEV='1'
$env:LECTIC_ORIGIN='http://127.0.0.1:8780'
$env:LECTIC_CLOUD_DATA='D:/tmp/lectic-pilot-preview'
$env:LECTIC_AI_BUDGET_MICRODOLLARS='1000000'
# Supply OPENAI_API_KEY through the process environment; never put it in the browser.
.venv/Scripts/python -m lectic.cloud.service
```

Open **http://127.0.0.1:8780**. Local mode uses a visibly labeled development account, SQLite and local private files. It cannot be enabled on a public origin. The current review instance uses a **$1 AI ceiling**, separate from the proposed $30 monthly pilot allowance.

FFmpeg and ffprobe are needed for media. Set `LECTIC_FFMPEG` and `LECTIC_FFPROBE` to their executable paths if they are not on PATH. The production image supplies them. Neither system Python nor an unrelated `DATABASE_URL` is reused for hosted data.

## Checks and release gates

Local checks include the original 280-test compiler suite, cloud ownership/idempotency/budget tests, starter install and sharing/revocation, compiler-home restoration, derivation round trips, scanned PDF and silent-video handling, TypeScript production build, and Android debug build/lint. Some media cases use deterministic fixtures; those do not establish real platform coverage.

Real model checks created a plan and a lesson from the **same Customer Discovery pack**. No extraction calls were needed for either. Model outputs that failed schema or semantic review were rejected rather than published. The live checks and current counts are recorded in [pilot review evidence](PILOT_REVIEW.md).

These gates are **not passed** merely because source code exists:

- Dedicated Supabase PostgreSQL migration, RLS/storage checks and live Google/Apple OAuth. Local tests inject two independent identities; they do not certify a deployed database.
- Render container build, persistent disk permissions, deploy interruption/restart and restoration from private Supabase storage.
- iOS compilation/signing on a Mac; installed iPhone and Android share testing, including expired auth, interrupted transfer and process termination. Android compilation is not a device test.
- Representative Instagram/X retrieval **from the actual host**, compared with the complete originals and the actual phone share payloads.
- Ten invited people: at least eight useful starter results within three minutes without coaching, plus one-week voluntary reuse and social fallback frequency.

## Input boundaries

Public link adapters require no Instagram/X API credentials, paid vendor or browser cookies. Every HTTP redirect is revalidated and connected to a pinned public IP. yt-dlp runs through a public-address-only, byte/time-limited proxy. Direct complete video files are supported when available; playlists/carousels, missing formats, blocked/deleted posts and unknown duration fall back rather than claiming complete retrieval.

This first implementation is intentionally conservative: Instagram/X static posts and carousels frequently need supplied screenshots; HLS-only video can need an upload; article pages need an identifiable article/main element. Actual coverage remains unmeasured. Comments, account crawling, threads, private posts, Stories and DMs are excluded. [yt-dlp itself cautions that listed extractors do not guarantee working retrieval](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

Uploads support UTF-8 text/Markdown/captions, PDF (up to 40 pages), JPEG/PNG/WebP, and common audio/video containers. HEIC and animated GIF currently ask for JPEG/PNG; unsupported or encrypted inputs retain the original and provide a recovery message. Image content is bounded to 25 megapixels. A video is not exhaustively visually analyzed: at most 12 frames are inspected and the resulting limitation is carried with the source.

Automatic transcript/OCR text and visual interpretations are separate source documents. Transcripts keep `caption_type: automatic`; old readers can identify them. Optional `sources/derivations.json` records source hashes, actual reported image model, processing version and page/frame/time references. It does not change the existing source/IR schemas. Pack exports include normalized source text, not private original media or the owner's full library.

## Deployment preparation (not provisioned)

Use `Dockerfile.pilot` and `render.pilot.yaml` only after choosing dedicated accounts and confirming actual charges. A proposed Standard Render instance plus a 20 GB disk is $30/month; Supabase Pro starts at $25/month. This leaves $30 for AI and $15 headroom under the $100 ceiling. These are planning amounts, not a billing quote. Recheck [Render pricing](https://render.com/pricing) and [Supabase pricing](https://supabase.com/pricing) before purchase.

1. Create a dedicated Supabase project. Apply the CLI-created migration in `supabase/migrations`. App tables have RLS; direct client writes are not granted. Only the API enforces uploads, invitation checks and quota. The private storage bucket grants owner reads only.
2. Configure Google and Apple providers, web redirects, and `lectic://auth` for the native PKCE callback. Set the invitation-only policy in Lectic; disable unwanted Supabase auth methods. Configure signing teams, app groups and Keychain groups for iOS.
3. Supply `LECTIC_DATABASE_URL` using the dedicated project's server credentials, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `OPENAI_API_KEY`, and an HTTPS `LECTIC_ORIGIN`. Never set `LECTIC_DEV` on the host. The database role must be able to check `auth.sessions` for immediate revocation.
4. Build and deploy the API/worker service. One persistent disk means deployment interruptions are accepted. No public signup or billing is included.
5. Invite at most ten accounts with `python -m lectic.cloud.admin invite person@example.com`. Revoking an invitation blocks subsequent authenticated API access.
6. Run all production gates above before distributing mobile builds or calling the pilot launch-ready.

The storage adapter sends new Supabase secret keys in `apikey`, following [Supabase's API-key guidance](https://supabase.com/docs/guides/getting-started/api-keys). Content-addressed upload retries accept the documented [already-existing-object response](https://supabase.com/docs/guides/storage/uploads/standard-uploads); they do not overwrite existing objects.

Defaults: 20 saved sources per pack; 100 MB per upload; 15 minutes per media item; 1 GB of originals per account. Server environment variables in `cloud/config.py` control limits. A changed text model requires explicit verified token prices. Requests stop at the application's paid-processing limit while library reads, copies and downloads remain available.

The spending ledger deliberately does not automatically retry a model request with an unknown outcome. An operator must compare the reserved call with provider usage first. This prevents duplicate paid work after a timeout. Successful calls and media checkpoints are reusable across worker restarts.

Backups retain the seven most recent committed compiler homes, with checksums and private storage keys. Older backup artifacts are pruned after the next successful backup. Supabase database backups separately protect metadata; private originals live in its bucket. **Full-host restoration and retention need operational rehearsal before the pilot**, including disk pressure from abandoned uploads. Do not confuse the tested compiler-home restoration with a complete hosted disaster-recovery test.

## Mobile builds

Android: open `apps/android` or run `gradlew assembleDebug lintDebug` with a JDK 17+ and Android SDK 35. Set `-PlecticOrigin=https://your-pilot-host` when building. The APK is an invited debug build, not a Play Store release. Production signing is separate.

iOS: on macOS, install XcodeGen, run `xcodegen generate` in `apps/ios`, open `Lectic.xcodeproj`, choose the signing team and configure `LECTIC_ORIGIN`, `LECTIC_APP_GROUP`, and `LECTIC_KEYCHAIN_GROUP`. Build the app and Share Extension together. The supplied CI job compiles the simulator target without signing; it has not been run as part of this local-only review.

Both companions copy files into private local storage before acknowledging a share. Files remain there through sign-in failure and network interruption. Opening the main app refreshes auth and exposes retry status. Creating results uses the responsive web library, which may require a separate browser sign-in. Real background lifecycle behavior must be verified on devices.

## Pilot measurements

`python -m lectic.cloud.social_probe links.json --environment render-pilot --output social-proof.json` records bounded retrieval outcomes without model calls. Supply a reviewed list of `{url, expected_type, expected_items}`. Do not substitute a local run for hosting evidence or a fixture for a real share.

`python -m lectic.cloud.admin report` reports first useful-result timing, return days, fallback actions and committed model spending. “Useful” is a user action; coaching and actual task success must be observed separately. Do not count developer preview sessions as pilot participants.

Deferred until after the invited pilot: desktop installers, browser extensions, ChatGPT/Claude connections, billing and public signup.
