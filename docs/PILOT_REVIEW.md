# Lectic pilot implementation review

Reviewed locally on September 26, 2026. Branch: `codex/cloud-pilot`.

**Verdict: the core value loop works locally. The invited cloud pilot is not launch-ready.** A person can choose a starter, request real work, inspect its sources, save a result, collect personal sources, assemble a pack, and share a fixed version. Hosted authentication, actual social retrieval coverage, phone lifecycle behavior and unaided user success still need evidence.

The owner requested local work and will supply different cloud accounts. No Supabase or Render resources were provisioned or changed. Work is isolated from the original checkout in `D:/Projects/lectic-pilot-worktree`.

## Are we overengineering it?

**Partly. The implementation is ahead of the value evidence.** A useful starter result, understandable references, saved work and a shareable pack prove the central idea. Account isolation, durable processing and spending controls are necessary when hosting other people's work. Building two native companions and broad social/media acquisition before observing unaided use adds complexity that has not yet earned its place.

Freeze feature scope. Start observing people using the current web flow now, then run the full ten-person acceptance study once authentication is configured. Keep one clear starting action and put advanced choices behind it. Ask whether someone understands what to do, gets useful work, shares it and voluntarily comes back. Simplify the flow wherever those observations expose friction. Local preview observations do not replace the hosted sign-in or phone acceptance gates below.

## What is good

- **The product now demonstrates its actual value.** The React application produces real work through the compiler and server-side model calls. It offers three immediately usable, Lectic-authored MIT teaching packs and six creation choices. The marketing animation remains clearly separate from real generation.
- **A pack is reusable.** A Customer Discovery pack produced both a plan and a lesson. A Startup Principles pack produced a plan and a checklist. These creations reused the existing knowledge without re-ingesting the sources.
- **Source inspection is part of the result.** Generated records pass the compiler's structure and evidence-link checks, followed by a separate assistant semantic review. Source statements, interpretations, adaptations and original advice have visible labels. References expand to the exact saved passage, with timestamps or page/frame labels where available.
- **Recovery preserves work.** Source capture and uploads precede processing. Failed retrieval keeps the original link and offers supplied content. Jobs, paid-call caching, upload retry keys, account leases and committed checkpoints survive local service restart. Uncertain paid calls retain their reservation instead of being silently repeated.
- **Privacy and spending have enforceable boundaries.** Ownership comes from server-validated authentication; private endpoints filter by owner. Share snapshots contain one pack. Cost reservations are transactional and global to the monthly application allowance. New paid work stops at the configured cap while existing work remains readable and downloadable.
- **The first screen is brief and visual.** Starter cards lead directly to a small brief and a Create button. Sign-in preserves the selected pack and brief; a reload preserves the active operation. Processing/provenance details stay behind disclosures.

## What is weak or unproven

- **Result presentation still needs simplification.** The final Debugging checklist rendered as a dense paragraph and included technical unit labels in its prose despite the prompt requesting clean prose. Expandable references work, but these presentation issues add reading effort. Clear checklist formatting and plain-language output are higher-priority improvements than another input channel.
- **Social import is a recovery-first implementation, with unmeasured coverage.** Instagram/X static posts and carousels generally require supplied screenshots; direct complete videos are attempted when the extractor provides a supported format. HLS-only, blocked, deleted, private and incomplete sources fall back. No actual Render-host retrieval measurements or real iPhone/Android share payload observations have been collected. Fixtures are not coverage evidence.
- **Generation reliability needs a broader evaluation.** Development runs exposed schema mismatches, inconsistent unit manifests, an overly restrictive semantic review and a response that exhausted its output allowance. Those failures were rejected and the driver was repaired. A fresh Startup checklist passed in one attempt; the Debugging checklist completed on retry after bounding the response fields. All three starters have produced real results, but this is not a measured success rate across all packs and formats.
- **Mobile code is ahead of device evidence.** Android compiles and passes lint. Swift app/Share Extension source and an XcodeGen project exist, but no Mac/Xcode build was possible here. Real expired-login, background upload, app termination and interrupted-network behavior remain untested on both phones. Opening the web library may require a second browser sign-in.
- **Cloud behavior is not established by SQLite tests.** The Supabase migration, RLS/storage policies, active-session validation, private backups and Render configuration are prepared. They have not been exercised together on dedicated accounts. Docker was unavailable locally, so the container itself has not been built.
- **Bounded processing has practical limits.** Uploads are capped at 100 MB, media at 15 minutes, PDFs at 40 pages and images at 25 megapixels. Video interpretation samples at most 12 frames and carries that limitation into pack-derived results. HEIC/GIF need conversion. Very large knowledge contexts can exceed the model processing limit. No exhaustive video-comprehension claim is justified.
- **Operations still need rehearsal.** Seven recent compiler-home backups are retained. Local restoration passed, but restoring an entire hosted service—including database metadata, private originals and homes—has not. Disk pressure, abandoned uploads, provider billing reconciliation and production OAuth must be checked before invitations go out.

## Evidence collected

| Check | Local result | What it does not prove |
|---|---|---|
| Existing compiler suite | 280 tests passed; 25 registry/pack/release regression tests also rerun after catalog changes | Hosted or phone behavior |
| Cloud acceptance tests | 30 passed | Live Supabase RLS or production auth configuration |
| Account isolation | Two injected identities cannot read or mutate each other's captures, jobs, packs, files, results, shares or backups; forged owner/path fields rejected | A deployed identity provider integration |
| Job and cost handling | Idempotency, interrupted upload, quota, cancellation after worker loss, account serialization, priority, backlog fairness, atomic reservations and uncertain calls checked | All possible host/process failure timings |
| Sharing and backups | Fixed-pack recipient copy, revocation, retained independent copy, home restoration and seven-backup retention checked | Full hosted disaster recovery |
| Media fixtures | Scanned-PDF page references, bounded oversized-page rendering, oversized-image rejection, silent-video frame inspection, unsupported files, private-address blocking and partial-carousel fallback checked | Real Instagram/X acquisition coverage |
| Real model calls | Text-source extraction/reconciliation, image OCR/interpretation, timestamped audio transcription, plan/lesson/checklist creation completed; all three starters exercised | Expert endorsement or independent correctness |
| Fresh final creation | Startup Principles checklist: **19.38 seconds**, one job attempt, 5 sections, 9 referenced units; actual model `gpt-5-mini-2025-08-07` | The 8-of-10, three-minute onboarding target |
| Local spending ledger | 34 paid-request records; **$0.130839** recorded actual cost, including the incomplete response; no unresolved reservations at review | A provider invoice or future monthly spend |
| Restart | API/worker restarted; saved packs, captures and results remained accessible; new work completed afterward | A deployed disk or crash during every processing stage |
| Published-reader compatibility | A media-derived `.lectic` export installed as **verified** with published `lectic==0.3.1`; automatic source labels remained identifiable | Every historic reader version |
| Web build/browser | TypeScript/Vite production build passed; real result, references, copy and Markdown download checked; 390 px viewport had 390 px document width; browser reported no console errors | Broad accessibility or cross-browser certification |
| Distribution preparation | Python wheel built and inspected for API/compiler/web assets/three packs; Android debug build and lint passed (0 errors, 12 warnings); Render YAML validated against its published schema | Signed mobile distribution, iOS compilation or a working container deployment |

Generated content was inspected as development evidence. It still requires human judgment. The compiler verifies that a quote occurs in saved text; it does not prove that the underlying advice, transcript or interpretation is true.

## Best path forward

1. **Resolve the plan's first proof gate on the dedicated accounts.** Confirm actual charges, deploy the container, apply the migration and validate auth/storage isolation. Test a reviewed set of Instagram/X posts, carousels, Reels, blocked/deleted links and actual phone shares against the complete originals. Publish the measured fallback rate and supported boundaries before promoting social acquisition.
2. **Finish phone validation before distribution.** Compile/sign the iOS app and extension on a Mac. Install both companions on real devices. Exercise URL/text/image/video sharing, expired auth, network interruption, process termination and retries, checking that every acknowledged item remains recoverable.
3. **Run the complete deployed acceptance suite.** Include two real accounts, exact citation inspection, different outputs from one pack, pack import/export, share revocation, worker interruption, backup restoration and the spending stop. Resolve defects before inviting nontechnical users.
4. **Observe ten people using the starter flow without coaching.** Measure sign-in-to-useful-result time and whether the output actually helps their task. Require at least eight within three minutes. Track social fallback and voluntary return over a week; do not substitute visits or developer feedback clicks for usefulness.
5. **Use those results to decide the next release.** First remove the largest measured friction. Keep desktop installers, browser extensions, assistant connections, billing and public signup outside this pilot until the basic value loop earns repeated use.

For local review, configuration, endpoint behavior and operational limits, see [PILOT.md](PILOT.md). README and the HTML pitch page describe the current implementation and its unpassed launch gates.
