**Lectic 0.3.1 release readiness**

Goal: make the current Lectic release ready today, preserving its complete save → prepare → apply → reuse → update → share experience. This checklist records implementation and verification; an unchecked item is not complete. The historical review remains unchanged.

- [x] Pack updates activate changed interpretations even with identical sources; prior builds remain valid; destination state is verified.
- [x] Shared collection/index mutations preserve independent writers and reject stale edits safely.
- [x] Packs have publicly verifiable signatures, bound publisher metadata, explicit trust status, and safe legacy handling.
- [x] MCP reads and capture/export paths cannot expose Lectic credentials.
- [x] Export inclusion/exclusion is consistent and explicit across CLI/MCP/team paths.
- [x] Inbox matching, partial selection, import failures, retries, and source-file retention work.
- [x] Saving without a named destination works immediately through Inbox; guidance reflects actual behavior.
- [x] Direct URL input routes correctly; unsupported content is retained with honest readiness states.
- [x] Setup checks configured local/remote servers and distinguishes configuration from client activation.
- [x] A real, bundled starter pack supports an offline first result, evidence inspection, and fresh-process reuse.
- [x] Registry search/inspection/install use real artifacts, validation, and honest unavailable states.
- [x] Publishing uses current pack content and validates recipient retrieval without unsafe replacement defaults.
- [x] One maintained public website accurately demonstrates the product and works on desktop/mobile; no false waitlist success.
- [x] README, setup instructions, skill/MCP guidance, cloud/phone docs, versioning, and dependency declarations agree.
- [ ] Regression tests cover the review's reproduced defects; complete Python suite and website checks pass.
- [ ] Built wheel/sdist operate from outside the checkout with bundled resources and the starter workflow.
- [ ] End-to-end local and HTTP journeys cover first use, reuse, update, backup/restore, and signed pack transfer.
- [ ] Release automation validates package and registry artifacts; release notes and final readiness evidence are written.
- [ ] Final requirement-by-requirement audit passes; publishing/deployment state is described accurately.

Not a release certification claim: a same-day engineering pass cannot establish population-wide superiority, retention, or willingness to pay. Those require the existing prospective user-study protocol. The release must state those limits and ship a concrete useful workflow that can be tested now.


Implementation checkpoint: core regression cases, actual local/HTTP connection checks, 390px mobile overflow checks, browser copy/verification actions and the archived React prototype build/lint have passed locally. The final full suite, rebuilt artifact evidence and platform CI remain pending below. Nothing has been published to PyPI or deployed by this task.
