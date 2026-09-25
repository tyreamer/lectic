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
- [x] Regression tests cover the review's reproduced defects; complete Python suite and website checks pass.
- [x] Built wheel/sdist operate from outside the checkout with bundled resources and the starter workflow.
- [x] End-to-end local and HTTP journeys cover first use, reuse, update, backup/restore, and signed pack transfer.
- [x] Release automation validates package and registry artifacts; release notes and final readiness evidence are written.
- [x] Final requirement-by-requirement audit passes; publishing/deployment state is described accurately.

Not a release certification claim: a same-day engineering pass cannot establish population-wide superiority, retention, or willingness to pay. Those require the existing prospective user-study protocol. The release must state those limits and ship a concrete useful workflow that can be tested now.


Local validation completed on 2026-09-25:

| Check | Result |
| --- | --- |
| Full Python suite, Windows / Python 3.10.9 | 280 tests passed in 172.705 seconds |
| Release regression cases | 11 passed; includes legacy key migration, signer continuity, same-source updates, Inbox retry/selection, credential boundaries, direct URL routing and real transport checks |
| Wheel and source distribution | Both installed into separate temporary directories and passed all seven release-gate stages from outside the checkout |
| First use and reuse | Two actual validated authored sample results; fresh interpreter and different project reuse the same saved result |
| HTTP journey | Real loopback MCP handshake, home lookup and starter reuse passed |
| Sharing and recovery | Public signature verification, changed interpretation over identical sources, preserved history, backup/restore and repeated merge passed |
| Browser | Chromium: 320px and 390px pages have no horizontal overflow; 1440px desktop inspected; copy, second-use interaction, source disclosure, keyboard skip link and actual pack checksum check passed |
| React reference prototype | Build and lint pass; fake waitlist removed; explicitly archived |
| Diff checks | No whitespace errors |

[Artifact checksums and reports](2026-09-25-artifact-checks.json) record the tested wheel and source distribution. The starter is a real 8,477-byte artifact with three cited procedures and one method, duplicated exactly into the public site's pack directory. Browser evidence is retained locally under `output/playwright/release-candidate/`.

All six platform CI jobs passed on runtime commit `d4422fdca550045be8962b42cf168cbd9ab34847`: Linux, macOS and Windows, each on Python 3.10 and 3.12. [CI run](https://github.com/tyreamer/lectic/actions/runs/36186223755). The final requirement audit passes for an alpha release candidate. No version tag, PyPI publication, merge to main or live site deployment has been performed by this task. The release remains an alpha: the useful starter is demonstrable, while comparative quality and retention still require user-study evidence.


Final audit decision: **ready to review and release as 0.3.1 alpha**. [Pull request #1](https://github.com/tyreamer/lectic/pull/1) contains the complete change. Subsequent evidence-only commits do not change the tested runtime. The wheel and source archive recorded above were rebuilt after the final method-readiness fix and each passed the installed-package gate.

The final method audit also confirms that packs exclude methods reviewed against earlier knowledge. Partial installs retain readable source material but do not present imported methods as ready until their evidence is reconciled and reviewed.

Release operations still to perform intentionally: review/merge the PR, publish the 0.3.1 tag through the existing protected PyPI workflow, and verify the live package/site after deployment. The task prepared and verified the release; it did not publish it. No original user knowledge, assistant configuration or signing credential was used for these tests.

The next product evidence should come from real users completing a first task, a fresh-session second task and an update task with their own material. Compare outcome quality and total effort with the same assistant and sources without Lectic. Keep the alpha label until those results justify stronger claims.
