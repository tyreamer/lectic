# Expertise Compiler: concept-validation testing guide

Bring material you trust. You don't need to know what to build: Expertise Compiler should show you its strongest supported opportunities, then build one you choose. If you already have a task, bring it too. The underlying expertise, evidence and methods should remain reusable for future work.

We're testing whether that saves effort and improves your work compared with attaching transcripts to an ordinary AI conversation. We haven't established that advantage yet. Honest failures and reasons you wouldn't use it again are especially useful feedback.

**For testers:** follow the numbered steps below with actual work. The facilitator operates comparison machinery and records measurements. **For the product team:** use the [study strategy](#product-team-strategy-what-we-are-trying-to-learn), freeze the decision criteria before seeing results, and avoid broad feature development until this pilot has produced evidence.

## The loop we can test today

| Stage | Current implementation | What this pilot must establish |
| --- | --- | --- |
| Source collection | Capture/import, transcript normalization, persistent collections and IR | People can supply usable material and reopen it without repeated preparation |
| Capability | Grounded Capability Map, direct selection and reusable method build | Suggested jobs are supported, understandable and worth doing |
| Baseline comparison | Matched prompts/tasks, saved context, structured response/citation checks and effort log | Independent runs and human review show whether the compiled method adds value |
| Refinement | An assistant can revise extraction or methods, preserve revisions and build again | A specific correction improves new work without damaging previously correct behavior |
| Validated artifact | Deterministic checks for current text outcomes and optional Agent Skills packages | The chosen artifact works on a new task in its intended environment |

**This is a facilitated loop, not an automatic end-to-end product promise.** Independent baseline execution, semantic judging, the correction-to-regression loop and evaluation-based release gating are not automatically orchestrated. Building a new artifact does not currently attach a behavioral certification; build validation explicitly reports effectiveness testing as not run. The pilot uses a separate evidence record rather than changing that claim by hand.

Test saved reviewers, decision frameworks, SOPs, guides, lessons and rubrics as **text methods**, plus optional skill exports. A rubric document is not an executable eval suite; a set of agent instructions is not a deployed agent. Standalone agents, persistent coaches, arbitrary exporters and automatic refinement are outside this study's shipped scope.

## Before you start

For the capture-first pilot, use the [iPhone Shortcut live test](iphone-shortcut.md#exact-first-live-test-from-your-iphone). It separately measures saving, sync and import before asking for processing. A URL-only capture is expected to remain unavailable for content-based work; that is different from a failed save. The rest of this guide tests discovery and useful outcomes once enough content is actually available.

Use local Codex or Claude Code with access to your project files and local tools. Follow the [installation instructions](../README.md#use-the-current-skill-interface); your assistant should handle setup, including checking Python 3.10+. You should not need to run compiler commands or edit JSON. If you already have an installation, ask the facilitator to verify its version before testing; the installer preserves differing existing installations instead of silently updating them.

Choose one project folder and keep using it throughout the test. Start with a small collection, such as 2–5 transcripts, so you can judge whether the assistant interpreted them correctly. This is a suggested pilot size, not a product limit. For compilation, supply UTF-8 `.txt`, `.md`, `.vtt` or `.srt` files. URLs and media can be captured, but V1 does not retrieve linked content or interpret raw audio, video, PDFs or slide decks. Ask the facilitator for help preparing text and include that preparation time in your feedback.

Use material you are authorized to process. For client or internal content, follow your organization's rules and redact where needed. Files are stored locally, but your chosen AI service may process their contents remotely. A plain web chat without local file and tool access cannot run this compiler autonomously.

## 1. Discover what your content can become

For the discovery test, give a normal user this exact prompt with their transcript files:

> Use Expertise Compiler with these transcripts. I think this material is valuable, but I don't know what I want to build. Save it as My Test Collection, show me the strongest things it could become, and recommend what to build first. Explain what I would give each one, what I would get back, and the important limits.

Check whether the ranked Capability Map helps you understand useful possibilities without having to choose technical formats. Does it explain why the sources support each opportunity? Are the ideas distinct and realistic, or attractive names for unsupported promises? A narrow map or an honest gap is better than five invented agents.

Reply **“Build #2”** (or name the opportunity you prefer). The assistant should build that saved opportunity directly, without asking you to translate it into an artifact type or resupply the sources. A reusable reviewer can be built before you supply a specific draft to review. Then try the finished method on real work and judge that result too.

If you already have a goal, you can bypass discovery:

Tell your assistant what you're trying to accomplish and what a useful result would look like. For example:

> Use Expertise Compiler to save these transcripts as Client Onboarding. I'm preparing a handoff for a new team member. Use the training to review my draft in ./handoff.md for missing steps and unclear responsibilities. Give me an improved handoff with reasons for the changes. Flag anything the training doesn't establish.

Use your own words. Share relevant context, a draft or decision if you have one, and any constraints or things to exclude. You don't need to pick a capability type or know compiler terminology. The assistant should ask focused questions only when it needs more information.

Some starting points for different kinds of work:

| Your work | A possible real task |
| --- | --- |
| Building with AI | Apply tutorial methods to review a design you're implementing; optionally export the method as a skill afterward. |
| Consulting or agency work | Use training content to improve an actual client handoff or SOP. |
| Creating or teaching | Use your own course transcripts to develop a lesson and exercise for a specific audience. |
| Knowledge-heavy professional work | Apply trusted training to a decision, plan or work product you already need to complete. |

These are examples, not a menu or guaranteed outcomes. The assistant should explain when your sources don't support the requested work. Current outputs include structured text results and optional skill exports; standalone agent exports and persistent coaching services are not available.

## 2. Check the first result

Read the actual deliverable, not just the completion message. Would you use it? What would you have to change first?

Check at least two important conclusions against their cited passages. Look for missing conditions, exceptions or disagreements. Can you tell what the source said from what the assistant inferred? If something is wrong, record the original result, the cited evidence and your correction. Corrections can be discussed in the session, but automatic correction propagation across future builds is not implemented yet.

The assistant should link to saved work and explain what was validated. A passing validator checks structure and evidence references; it does not prove the interpretation is correct or the result is useful.

## 3. Come back with different work

Start a fresh assistant session in the **same project folder**. Name the saved collection and describe a different goal. For example, use the onboarding training to create a new starter's first-week checklist after reviewing the handoff.

Don't reattach the original transcripts. Check whether the assistant finds the collection, reuses its expertise and produces the new result. It may need to read archived sources again for knowledge the first task didn't require. That is different from asking you to upload everything again.

Record any repeated explanation, missing context or manual help. Collections are project-local; opening an unrelated project is not expected to find them automatically.

## 4. Change the source material

Add one relevant transcript, or supply a revised file and explicitly ask to replace its earlier version. Ask what changed and rerun an affected task.

Check whether the new result accounts for the change and whether the earlier result remains available. Also ask “What changed in the Capability Map after adding these sources?” Check the explanation against the material: new support, weakened ideas and disagreements should remain visible, and the earlier map should remain available. If no relevant conclusion should change, saying so is a valid outcome. Record stale advice, lost history or repeated setup work.

## 5. Compare with ordinary transcript chat

Use a separate conversation with the same model where practical. Give it the same complete sources, real task, constraints and requested result, but don't give it the compiler's extracted knowledge, method or answer. Let both approaches retain their own saved context for later tasks. Don't make the baseline start from scratch each time while allowing only the compiler to remember.

Repeat the different-goal and source-update tasks in both approaches. Record initial setup and preparation separately from later effort. If possible, have someone review the answers without knowing which approach produced them. A small pilot provides observations, not proof of general superiority.

| Compare | What to record |
| --- | --- |
| Usability | Setup problems, questions you couldn't answer, facilitator help required |
| Useful work | Whether you'd use the result and the edits still needed |
| Faithfulness | Unsupported statements, missed conditions, lost disagreements, incorrect citations |
| Effort | Approximate minutes and corrections for first use, reuse and updates in each approach |
| Return value | Whether you'd bring another task or collection, and why |

The [evaluation protocol](EVALUATION.md) has more detail if you want a structured comparison. Ask the assistant to handle its mechanics.

## 6. Refine once, then test something new

Choose a concrete problem in a development example: an omitted condition, misinterpreted passage, lost disagreement or unusable instruction. Record the original interpretation, exact evidence, your correction and the expected behavior. The assistant can make a revised extraction/method and a new build; this is a manual pilot exercise, not an implemented automatic correction system.

Keep the source originals, original method/build and first result. Use a separate, previously unseen task to check the revision. Do not label the corrected development example a held-out test. Check both the behavior that needed fixing and one previously correct behavior. If the final test fails and you tune against it, it becomes a development case; reserve another unseen task for any further effectiveness claim.

Give the baseline the same relevant factual correction, task information and feedback opportunity in its own workspace. Include correction, rebuild and verification time in both arms. Don't give only the compiler unlimited retries. Capture useful failures even when there is no time to repair them.

## 7. Use the artifact, not just its completion message

Use the final text method in a fresh session on the reserved task. If you actually need a skill, ask for an export and have the facilitator help load it in the intended client. Verify that it uses the expected method and handles missing inputs. Keep installation help and runtime failures in the record. No need to export every method or test every future format.

Describe the result narrowly: **“Structurally valid; reviewed against these sources; passed these specific tasks in this environment.”** Never shorten that to a general guarantee of correctness. Exported packages should not contain private briefs, unrelated full transcripts or the held-out answer key.

## Share your feedback

Send this short report to the person who invited you. You can omit confidential material; include sanitized examples only when permitted. Don't upload your whole `.expertise-compiler` folder—it contains original content and private work.

```text
Assistant/client and model:
Compiler version or commit (ask the facilitator if unknown):
Material: domain, file count, approximate length:
My initial goal, if any, and what success meant:
Capability Map: useful opportunities? Unsupported suggestions? Clear inputs/outputs?
Selected opportunity: did it build directly without an asset-type question?
Setup/preparation effort and help needed:
First result: usable / usable after edits / not usable, because:
One interpretation or evidence problem, if any:
Fresh-session second task: found the collection? Re-upload needed?
Source update: reflected correctly? Earlier result and map still available?
Comparison with ordinary chat: better / similar / worse / not run:
Approximate effort for each approach: first task / second task / update:
Refinement: what was corrected, what changed, and did the unseen task improve?
Artifact used: text method / skill; client and fresh-session result:
Would I use this again for actual work? Why or why not?
Biggest friction or missing capability:
```

If a step fails, save the error or a sanitized excerpt and tell the facilitator. Don't spend the session debugging internals. An unfinished test still gives us useful evidence.

## Product-team strategy: what we are trying to learn

The hypothesis is that people who repeatedly apply trusted human methods can save meaningful work by compiling expertise once, choosing supported capabilities, and reusing/correcting them across tasks. Capture and discovery reduce the effort required to reach that value. Neither capture counts nor attractive capability names demonstrate it by themselves.

Test four questions separately:

1. **Discovery:** Can someone who has no build idea identify a useful, source-supported opportunity without coaching or artifact jargon?
2. **Application:** Does the compiled method produce work the person would actually use, compared with capable ordinary transcript chat?
3. **Accumulated value:** Does a second goal, a source update or a correction cost less effort while preserving fidelity and history?
4. **Return behavior:** Does the person voluntarily come back with another real task because keeping the expertise is useful?

The current 100 passing automated tests are implementation evidence, including authored cross-domain fixtures. They do not establish any of these product hypotheses. The repository snapshot at the start of each study, not a rolling test count, identifies the implementation being tested.

## Recruit people with repeated work, not just AI enthusiasm

Use 10–14 participants across the groups below. Select people who know their source material well enough to recognize a bad interpretation, have permission to use it, and have at least two relevant tasks coming up. Include ordinary users of their chosen assistant, not only people experienced in building skills. Avoid recruiting solely friends who want to support the project.

| Group | Total participants | Material and real work to test | Main question |
| --- | --- | --- | --- |
| Vibe coders / AI builders | 4–5 | Tutorial or technical-talk transcripts → review a real design; then a troubleshooting guide or optional reusable skill | Does this save repeated prompting and produce a method worth integrating? |
| Consultants / agencies | 2–3 | Authorized client training or SOP text → review a handoff; then improve a procedure or onboarding checklist | Does it save delivery/review work while preserving client-specific limits? |
| Creators / educators | 2–3 | Their own course/video transcripts → review a draft or lesson; then create an exercise or bounded creative-method guide | Does it faithfully reuse their methods without inventing authority or promising a persistent coach? |
| Knowledge-heavy professionals | 2–3 | Training/talk transcripts and worked examples → make a contextual plan or decision; then review a work product | Can people outside the AI-builder niche get useful work without understanding compiler internals? |

Maintain the builder-oriented product direction. Personal Dinner Ideas captures are a useful domain-neutrality and capture test, not a reason to turn the pilot into a recipe-product study. Use low-consequence tasks where a participant can review the output before relying on it; evaluate drafts and practice cases for high-stakes professional domains.

Record the participant's existing workaround: ordinary chat, a saved project/prompt, manual notes, a checklist or another tool. The controlled baseline is ordinary transcript chat; their real workaround provides an additional relevance check. A compiler win against a weak baseline can still be irrelevant if their current workflow already does better.

## Run two waves and stop expanding scope

**Preflight:** use a pinned checkout or verified fresh installation. Test the whole path in each client you will advertise: saved content → map → selection → usable result → fresh-session reuse → optional skill use. Confirm paired prompts actually run in isolated contexts. For capture, separately verify one actual phone URL/text save and desktop import. Use the [acceptance protocol](UNIVERSAL-ACCEPTANCE.md); the Shortcut remains a device-test requirement, not something unit tests certify.

**Wave 1: four guided participants, one per group.** Observe setup, discovery and first use, then a second task in a new session. Record every intervention. Resolve repeated blocking failures before expanding; aim for all four to reach a usable saved result with disclosed assistance and to understand what remains unsupported. Use this wave to fix the study protocol and critical defects, not to optimize each person's answer until it looks impressive.

**Wave 2: the remaining 6–10 participants.** Freeze the revised instructions, build version, comparison design and decision criteria. Give the same short onboarding and let participants attempt the tasks before helping. Cover both Codex and Claude Code among the AI-builder testers if both are in the supported claim. Report guided and less-assisted waves separately; do not blend rescued runs into an unassisted completion rate.

Use roughly a two-week observation window. Start with a first-use session, follow with a fresh-session task and source update on later days, and include one bounded correction/new-task check. Budget about 60–90 minutes of active testing per participant across sessions; record actual time rather than hiding overruns. The baseline should be run by the facilitator or assistant where possible so the participant's time goes to judging useful work. Extra large-corpus stress tests can be internal, not homework for every tester.

After scheduled tasks, leave an opportunity for voluntary return. A required follow-up is not retention. Record self-initiated use separately from reminder-driven use. Fix data loss, wrong source attribution and blocking bugs immediately; log version changes and rerun affected checks. Defer new exporters, hosted interfaces and broad automation until the decision review.

## Choose corpora and tasks that could disprove the idea

Start with 2–5 supplied text/transcript files per participant, then include a few larger real collections among willing builders after the basic path works. This is an initial study size, not a supported product limit. Spread the following evidence shapes across the cohort rather than asking everyone to run every case:

| Evidence shape | Test task | Desired behavior / failure to watch for |
| --- | --- | --- |
| Procedures and worked examples | Diagnose or review new work | Applies source-specific steps and conditions; not generic advice with citations appended |
| Mostly factual material | Ask what it can become, then request an unsupported reviewer | Recommends bounded reference/learning uses and explains missing judgment; no invented procedural agent |
| Conflicting experts | Compare a decision or evaluate a proposal | Preserves separate positions and their applicability rather than averaging disagreement away |
| Sparse or incomplete material | Produce a contextual plan | Asks for essential missing details or marks uncertainty; no invented quantities, criteria or transcript |
| Personal qualification | Apply a method with “not company policy” or “use only this part” | Preserves personal context separately and respects the requested use boundary |
| Changed source | Add a contradicting update, then revisit the task/map | Explains changed support and leaves earlier maps/builds inspectable |
| Same corpus, different goal | Review first, then plan/teach/create | Reuses or extends saved expertise without another source upload or forcing the original format |
| Saved links plus supplied text | Import, then request useful work | Distinguishes saved from retrieved/processed and uses only available content |

Give 2–4 participants an optional capture track across the existing groups. Let them save a few items encountered naturally, including a URL-only item and actual shared text. Record save success, sync delay, import retries, repeated-import duplicates, annotation handling and a later real use. Don't hand-curate every capture into a complete transcript. Failed retrieval is an expected V1 limitation; if users consistently need link-to-content retrieval to get any value, that is still a product finding, not a problem to hide by silently preparing sources for them.

Use the new four-action Shortcut recipe for fresh installs; keep a legacy-format case in the facilitator's compatibility checks. Measure installation minutes separately from recurring save time, and record every intervention configuring variables, dates, filenames or folder permissions. Check that the JSON timestamp reflects the phone capture time even after delayed sync; rename a file while retaining `.capture.json` and reimport without duplicates. Device-test the date formatting and dictionary serialization before claiming easier onboarding. A smaller action count alone is not evidence that users can set it up unaided.

Use a relevant supported job as the primary application task when the material permits it. Keep deliberately unsupported requests as separate diagnostic probes: an honest refusal can pass a fidelity check without counting as a completed useful artifact. If a person's actual material supports no useful job for them, record that unmet need rather than inventing an opportunity or quietly replacing their corpus.

## Make the baseline comparison fair

Before either arm runs, freeze source bytes/revision, task inputs, context, success criteria and a rubric. Use the same model/settings and tools where controllable; record differences if not. Give both arms the same complete available sources and personal constraints, including unavailable-content flags. The compiled arm also receives the compiled method and evidence. Both may keep their own notes, methods and persistent context across later tasks. Include source preparation, installation, compilation, waiting, repairs and evidence checking in the effort record.

Separate compilation/development examples from final tests. Ask the participant to reserve real work or have an independent reviewer prepare cases before compilation. Keep answer keys outside both model contexts. If independent cases aren't available, label assistant-authored cases honestly. A session that has already seen the compiled method cannot serve as an uninformed baseline.

Use paired tasks for **initial use, reuse and source update**, plus one bounded refinement exercise and an untouched transfer/regression check. Run exactly the same task in each isolated arm; alternate which arm goes first across participants. Show answers as A/B where feasible, vary display order, and conceal the origin from the reviewer. Blinding may be imperfect because formats differ; record when it is broken. Equalize feedback/retry budgets in advance, for example one correction round per arm, then record failures rather than retrying indefinitely.

Keep the baseline capable: ask it to solve the task using the supplied methods, explain relevant evidence and state unknowns. Let it save a reusable prompt or checklist if that is part of normal chat use. Don't force it to forget context, give it less material, or compare a carefully edited compiled answer with its first unreviewed draft.

Comparison preparation and deterministic scoring use the existing [evaluation harness](EVALUATION.md). Independent session execution, human meaning review and refinement remain facilitated. Do not claim automatic evaluation because the assistant produced both answers in its informed conversation.

## Record behavior and effort, not only ratings

Use the existing `effort.json` for baseline/compiled × initial/reuse/update. Keep a separate study worksheet for discovery, refinement, final artifact use and voluntary return. These additional fields are a research protocol, not new executable evaluator support. Record unknown values as unknown, never zero.

| Measure | Operational definition |
| --- | --- |
| Unassisted completion | Participant obtains usable work without the facilitator editing compiler files, repairing JSON, choosing an opportunity for them or writing the result |
| Discovery usefulness | Participant identifies a specific useful job in the map without being coached; an explicit lack of supported opportunities can be the correct outcome |
| Useful output | Participant can use the result as-is or after minor edits that do not repair its core reasoning |
| Faithfulness | Human checks decisive claims against source passages, including conditions, conflicts and source-versus-note attribution |
| Active effort | Participant and facilitator minutes separately, including preparation, prompts, verification, corrections and failed attempts |
| Waiting / usage | Assistant elapsed time and observable token/usage data when available; don't invent model costs |
| Reuse | A fresh session finds the collection and completes a new task without asking for already saved sources |
| Refinement transfer | The documented correction helps on a new case without breaking a previously correct behavior |
| Artifact fitness | Text method or skill is usable in the named target client on reserved work, beyond passing a package validator |
| Voluntary return | A self-initiated additional real task or collection outside required study steps, with the reason for returning |

Rate usefulness using anchored labels: **unusable**, **major revision required**, **usable after minor edits**, **usable as-is**. Record critical errors separately so a polished output cannot average away a serious source misrepresentation. Define task-specific critical errors before testing, such as inventing unavailable source content, reversing a source's recommendation, dropping a decision-changing exception, or presenting a personal note as established policy.

Human reviewers should know the domain/source content. Review at least the decisive recommendations and two additional source-linked claims per output, not merely two easy citations. Keep quality, effort and trust as separate observations. No fake confidence score or single automatic “winner” replaces these checks.

## Proposed decision gates: freeze before Wave 2

These thresholds are **proposed product decisions**, not scientific benchmarks or existing results. Adopt or revise them once before the second wave, record the choice, then don't move them after seeing outcomes. Report raw counts alongside percentages, by wave and group. With 10–14 testers, treat findings as directional evidence and failure diagnosis, not proof of population-wide superiority.

| Gate | Proposed threshold | If missed |
| --- | --- | --- |
| Basic usability | At least 80% of Wave 2 participants complete their first usable result without facilitator repair | Fix onboarding/operation before broader recruitment |
| Fidelity and preservation | No unresolved critical source misrepresentation in artifacts delivered as validated; no observed loss of captured material or historical assets | Stop the affected flow, repair and rerun its checks |
| Value over chat | At least 60% of Wave 2 participants show a paired value win across initial/reuse/update, not just one cherry-picked answer | Examine whether benefits are too generic or upfront cost is too high |
| Durable reuse | At least 80% of Wave 2 participants complete fresh-session reuse without re-uploading saved sources | Fix collection/session behavior before adding targets |
| Return value | At least half of Wave 2 participants initiate another real use outside required tasks during the observation window | Reconsider frequency of need and whether outputs earn repeat use |

A **paired value win** means either comparable acceptable quality with a reduction in total active effort that the participant declared worthwhile before seeing answers, or a meaningful predeclared improvement in usability/quality without unacceptable extra effort. Set the effort/quality threshold per task before running it; do not invent savings from elapsed model time alone. Count compiler setup in the initial cost. Report initial cost and later savings separately even when their sum is unfavorable.

Use all enrolled Wave 2 participants as the denominator for product completion/value gates. Incomplete tests, unavailable content and blocked setup remain visible; don't silently drop them to improve the rate. Also report complete-pair results separately to explain mechanisms. Group multiple tasks under their participant rather than treating them as independent people. Keep one group's strong results from masking another group's consistent failure.

For capture, require lossless retention of the accepted test records, zero duplicates on repeat import of the same IDs, preserved notes and honest availability states. Record the full attempt count including failed phone saves. Do not equate record count with useful expertise or interpret storage success as concept validation.

## Turn the evidence into one next decision

Hold a review after the observation window using a participant-level ledger: group, client/version, source shape, discovery result, paired quality/effort, help required, reuse, correction transfer, artifact use, return behavior and failure reason. Bind each reported artifact to its build/IR/source hashes, environment, evaluated cases, validation report and human review. Use labels such as **structurally checked**, **human source-reviewed**, and **tested on these cases**; don't add a blanket “validated agent” badge.

- **Continue narrowly** if the gates pass and repeat value appears in real work. Build the one improvement tied to the most consequential observed bottleneck.
- **Focus recruitment/use cases** if value is concentrated in one recurring job or group. Keep the core domain-neutral; this is evidence about where to test next, not a reason to add hard-coded niche logic.
- **Fix and retest** if quality is useful but installation, capture acquisition or session reuse prevents access to it.
- **Reconsider the premise** if ordinary chat matches quality and effort across repeated tasks and people don't return. More output formats won't establish differentiation.

The eventual automatic loop still needs reliable isolated execution, bound evaluation results, versioned corrections and regression checks, and target-specific acceptance gates. Do not build that machinery merely to complete a diagram. First run this facilitated loop and establish that its successful outcome is worth automating.
