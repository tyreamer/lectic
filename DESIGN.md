# Design: compile expertise, preserve evidence

The canonical product direction is [NORTH_STAR.md](NORTH_STAR.md). The core compiles reusable expertise; an installed skill is one interface, and Agent Skills is one output format. The source collection and IR must outlive any provider, runtime, interface or target.

## Core, target and interface boundaries

Conceptually, `expertise-core/` owns sources, collections, IR, extraction/reconciliation, goals/build intent, selection/compilation, provenance, versioning, validation and evaluation. `targets/` contains consumers of those contracts: skill, agent, workflow, reviewer, coach, eval, knowledge-pack, custom and future targets. `interfaces/` contains Codex/Claude skills and CLI today, with desktop, web, API or MCP as possible later adapters. These are responsibility boundaries, not newly implemented directories or a commitment to ship all of them.

The conceptual pipeline is collection → durable IR → build intent → select/extend relevant expertise → compiled method/capability → target artifact → validate/evaluate → portable output. Selection must leave the original IR intact. New extraction extends a versioned representation; changing a target must not require re-ingesting the corpus. An artifact can be a useful direct result or an exported capability. Validation may precede a later runtime evaluation; portability does not imply effectiveness has been measured.

Build intent ultimately needs independent inclusion/exclusion choices: reasoning without personality, interview techniques without unrelated knowledge, language tendencies without opinions, or a multi-expert reviewer that preserves disagreement without imitating its sources. Current free-text briefs can describe these requests, but structured selection enforcement is future work. Existing intents describe purposes, not all possible artifact types; future targets must be extensible without turning the IR into a list of provider or exporter formats.

| Responsibility | Current implementation | Boundary to preserve |
| --- | --- | --- |
| Capture and personal context | scripts/capture_store.py; capture schemas | Saved input and annotations are distinct from source truth |
| First capture adapter | scripts/capture_input.py; scripts/capture_write.py; docs/iphone-shortcut.md | Synced-folder transport independent of compiler/provider |
| Sources, IR, validation | schemas and parts of scripts/ec.py | Provider-neutral source and knowledge records |
| Collections and revisions | scripts/collection_store.py | Durable private archive independent of builds |
| Storage location and primitives | scripts/home.py; scripts/store.py | One home per user; blobs, staged publish and transactions are the only filesystem-specific operations |
| Opportunity discovery | scripts/capability_maps.py; discovery prompt | Replaceable, versioned interpretation of IR |
| Library and next-use guidance | scripts/library_guide.py; use-guide schema; guide-use prompt | Read actual saved state; keep personal applications separate from IR and exports |
| Goals and compilation | scripts/goal_workflow.py; extraction/reconciliation prompts | Interpret intent, select expertise and preserve evidence |
| Current text outcome targets | scripts/outcomes.py | Rendering and goal contracts, not an exhaustive expertise taxonomy |
| Agent Skills target | scripts/scoped_export.py; rendering in scripts/ec.py | Scoped export consuming core records |
| Evaluation | scripts/evaluate.py and evaluation prompts | Distinguish integrity, meaning and observed behavior |
| Assistant interfaces | SKILL.md, agents/openai.yaml, operator prompts, installer | Gather intent and operate core; no provider dependence in IR |
| CLI interface | command dispatch in scripts/ec.py | Invoke core operations; do not define the product |

New capture and discovery modules sit alongside the existing compiler without moving its public entry points. The installer includes their contracts, prompts and documentation, including the north-star document, so the distributed interface retains the architecture guidance.

## Remaining structural coupling

The implementation is useful but not yet a fully separated core package:

- `ec.py` mixes core validation/parsing with CLI dispatch and skill rendering; other modules import it. Split responsibilities incrementally while preserving public commands and artifact formats.
- `goal_workflow.py` coordinates assistant prompt paths and specific renderers/exporters. A later core compilation contract should accept reasoning results independently of the installed interface and dispatch targets through explicit contracts.
- `outcomes.py`, CLI choices and schemas enumerate eight intents and a closed set of section kinds. They are today's supported contracts, not an extensible target registry. Do not add one new core enum for every future use case.
- Compiled methods reuse a capability schema with skill-oriented IDs, required steps and examples. This is distinct from the IR, but not yet a neutral representation for every profile, evaluator or custom target.
- The IR has a closed unit-type enum; conditions, exceptions and some style/reasoning characteristics currently live in statements, scope, derivations and relationships. It does not yet provide typed, independently selectable components for the full north-star taxonomy. Evolve it with versioned compatibility rather than assuming today's labels are exhaustive.
- Build intent has no structured include/exclude contract or correction revision. User instructions can guide reasoning but exclusions are not deterministically enforced, and corrections do not yet propagate through a durable regression loop.
- Compiler fingerprints include the installed SKILL.md. This conservatively tracks current instruction changes, but eventually core, reasoning-interface and target versions should be recorded separately in build manifests.

These are explicit follow-up constraints, not implemented features or reasons to rebuild the entire project. Canonical source and IR schemas currently contain no mandatory provider-specific fields, and existing records remain unchanged.

## Storage: one home, cloud-shaped

`home.py` resolves where knowledge lives: `LECTIC_HOME` if set, else a project's existing `.expertise-compiler/` when it actually holds storage (legacy project-local mode), else `~/.lectic`. Collections, captures, builds, exports and legacy runs all live under that home, so every project and every assistant on the machine reads the same library. Per-project state that must stay separate (the legacy numbered-capability session) is keyed by project inside the home. Session pointers written by project-local installs still resolve.

Everything persisted is one of two kinds. Immutable objects: content-addressed blobs (`HOME/blobs/<sha256>`) and validated snapshots (source revisions, builds, maps, packages), written once and never edited. Small mutable indexes: `library.json`, `collection.json`, capture state. `store.py` owns the three operations that need a filesystem: `put_blob`/`get_blob`/`materialize` (a snapshot gets its raw bytes by hard link where possible, by copy otherwise; the blob store stays canonical, so nothing requires hard-link support any more), `stage()` (assemble beside the destination, publish by one rename, discard on error, never merge into an existing snapshot) and `transaction()` (serialize index writers). Nothing above this module links, renames or locks directly. A remote store implements the same three operations with object storage and compare-and-swap; because identities are content hashes, the immutable side needs no merge logic and only the small indexes need CAS.

What this pass deliberately leaves for later: `units/`, `history/`, `state/` and similar directories are still enumerated with `glob`, because the assistant writes checkpoint files into them directly. Moving those writes behind tools (a local MCP server) is what makes index files, and therefore a remote store, viable. The sequence is: shared home and store seam (done) → tools instead of direct file writes → remote store behind the seam → phone captures posted to it.

## Capture layer before the compiler

The architecture now includes capture → sources/collections → expertise compiler → builds/outcomes. `capture_store.py` owns immutable envelopes, attachment blobs, annotation events and mutable membership/processing state. `capture_write.py` is a reference producer for the generic folder contract. The iPhone Shortcut is a first adapter described in `docs/iphone-shortcut.md`; there is no iCloud API in the core, native application, hosted backend, watcher or retrieval service.

Capture and annotation schemas are independent of source and IR schemas. A capture preserves original shared value, known URL/title/type, attachment references, timestamp and entry provenance. A separate state record tracks import identity, multiple stable collection IDs, normalized source IDs and processing issues. Notes never enter normalized segments. New build briefs snapshot relevant capture context privately; later notes cannot mutate old builds or become source evidence. Trace operations follow cited result units to historical source IDs and then to captures.

The minimal share adapter only requires original shared content and capture time. `capture_input.py` expands `.capture.json` inputs into the existing canonical schema at import: stable identity, URL detection, type, status and provenance belong on desktop, where they are testable and updateable without rebuilding each phone Shortcut. Capture time must still come from the producer, since sync/import time is not capture time. Personal notes remain separate optional fields. The four-action phone recipe and full legacy records feed the same core; the core never assumes that a file's adapter label authenticates its originating device. See the [minimal input contract](docs/CAPTURE.md#minimal-share-input-adapter) for timestamp/identity and same-time duplicate semantics.

Import is idempotent by capture ID and envelope fingerprint. Attachment blobs are content-addressed; different intentional captures may retain separate notes while sharing source content. A repeated ID with different data is an error, not an update. Synced JSON records are commit markers written after attachments. Missing files and early annotation events retry on a later explicit import. Original synced files remain untouched. A local OS writer lock serializes capture CLI mutations and releases on process exit; the project does not merge competing desktop replicas.

Normalized captures live once in a canonical source store, and raw bytes live once in the home's blob store. `Library.attach_shared` records memberships as existing-format immutable source snapshots whose raw files the store materializes from those blobs (hard link where the filesystem allows it, copy otherwise). Thus current source validators, evidence paths and build formats remain compatible, no payload is stored twice where the filesystem can share it, and no filesystem prerequisite remains. Legacy ingestion registers its bytes with the same blob store; earlier snapshots are not rewritten. Private snapshots and canonical source files should be treated as immutable; hashes detect tampering.

Explicit processing normalizes supplied text, eligible transcript attachments and successfully retrieved captions. `linked_sources.py` owns linked-source routing and an immutable, hash-verified acquisition cache; the first retriever is YouTube via an optional local `yt-dlp` executable. `capture_store.py` calls this generic boundary only during processing. It records retrieval separately from normalization and saved IR coverage; successful captions do not automatically mean processed. Exact capture URLs and personal notes survive canonical video identity deduplication. [Acquisition contract](docs/YOUTUBE.md).

Processing reuses verified source-local checkpoints from current or historical collection revisions when evidence, IDs and relations remain compatible. Cross-source synthesis still needs reconciliation. Nothing recompiles on import, and no broad dependency-rebuild system is added. Processing statuses distinguish saved data, unavailable linked content, partial work, a saved IR representation and issues. A validated representation is not truth or proof that all expertise was extracted.

Relationships currently use explicit capture IDs, source IDs, collection IDs, annotation IDs and build/IR evidence links. Graph-style traversal can be introduced later if useful; no graph database is needed. Membership removal preserves historical originals; a capture with no remaining named membership returns to Inbox. Capture state lives in the shared home, and the synced intake is not bidirectional synchronization of compiler state. See [capture contract](docs/CAPTURE.md) for exact storage and failure behavior.

## Capability Maps: derived opportunity discovery

The optional exploration path is collection → durable IR → Capability Map → selected build intent → compiled method → result/asset. A known goal bypasses discovery. `scripts/capability_maps.py` owns binding, validation, qualitative ranking, immutable map persistence, comparison and selection. The skill and CLI are interfaces to it; assistant reasoning follows `prompts/opportunity-discovery.md`. No model SDK, domain-specific branch or source recommendation field is added.

`capability-map-draft.schema.json` records semantic assessments of ten universal transformation categories and up to eight distinct candidates, including useful weak gaps. `capability-map.schema.json` binds the reviewed draft to collection/source revision, full IR hash, compiler version/fingerprint and discovery method version. Canonical content hashes identify map revisions. A collection's `maps/` directory stores JSON and readable Markdown; `maps/index.json` preserves history and the last shown map. Drafts are resumable. Original IR and its history stay separate and unchanged by map generation.

Ranking is qualitative and lexicographic: support, reuse, actionability, saved work, judgment, differentiation from Q&A; stable ID resolves ties. Up to five non-weak opportunities are shown. Exact source counts are derived from evidence, not confidence scores. Validators require known evidence IDs, typed procedural/criteria support, examples and conditions for strong actionable opportunities, all recorded contradictions touching a selection, current delivery forms and complete internal category assessment. These checks cannot establish entailment: the assistant must assess whether examples, criteria and conditions actually support the proposed job. A misleading title or prose claim is not reliably rejected by type checks alone. Live discovery quality remains unmeasured.

Comparison uses stable job IDs and reports new, removed/invalidated, stronger/weaker, newly supported, conflict-affected and evidence-changed entries. Support changes reflect assistant judgments, not measured improvements. Source changes require preparation and regeneration; stale selection is rejected. Historical maps validate against historical IR. Identical regeneration is idempotent; changed interpretations create new map IDs without overwriting old maps.

Selecting a shown number or title stores the full opportunity and map ID in a private build brief, including evidence, input/transformation/output, future use categories, boundaries, conflicts and targets. The normal pipeline then assesses coverage and builds a reusable text method through its existing CREATE contract, without needing a sample user draft or technical artifact choice. This is intentionally distinct from applying that method to an actual review task. Skill export remains explicit. Opportunity categories AUTOMATE and EVALUATE do not add executable workflow or eval-suite targets; portable instructions and rubrics can be produced as text, while unavailable integrations remain marked future.

The existing legacy numbered capability flow remains available. The old `work` missing-goal response remains a compatibility fallback; the updated conversational adapter routes goal-free content to maps. The current map module still calls the goal coordinator for preparation/builds, so the eventual provider-independent core API split remains future work. Correction propagation and behavioral regression evaluation remain the next major quality direction.

## Universal goal compilation

The architecture separates collection, durable IR, user brief, compiled method, result and optional exported asset. A collection can support CREATE, REVIEW, IMPROVE, DECIDE, PLAN, DO, LEARN and REFERENCE. These are internal outcome contracts, not product niches or a user menu. The host assistant interprets natural language and records intent plus reasoning in the brief. Python validates and routes this decision; it has no domain classifier or domain-specific branches.

New outcomes use schema version 1.1. Typed sections carry useful work and epistemic labels. Source-derived sections cite selected units; original creations and user context remain separate. Minimal intent contracts require, for example, options plus recommendation for DECIDE or lesson plus exercise for LEARN. These checks detect missing structure, not meaningful analysis or learner mastery. The assistant supplies and reviews semantics.

Legacy 1.0 review/checklist results retain their schemas, rendering and package validation. New intent-bearing briefs produce outcome builds with a readable method and relevant evidence; a skill package is generated only on explicit export. The method retains the existing evidence-linked capability structure. Compiler fingerprints include root SKILL.md, scripts, prompts and schemas.

Collections support preparation without a goal, summaries, addition/replacement/removal, history comparison, archive/restore and reuse. Removing the final active source creates an empty source revision and preserves history. Missing evidence invalidates knowledge and its transitive relationships; valid partial knowledge is retained for a targeted pass. Earlier builds validate against their historical IR and originals. Explicit knowledge hashes permit comparisons within a source revision.

Archive is a reversible lifecycle flag, not deletion. Explicit named use restores an archived collection. “Just save for later” preserves originals; “Save these as NAME” can prepare knowledge without inventing a goal, result or skill. Later goals, from any project on the machine, do not need source re-upload. This iteration adds no accounts, hosted storage, networking, model APIs, agent teams or ingestion integrations.

## Current conversational interface

The installed skill is an interface/adapter to the core compiler, not the canonical product surface or architecture. Users supply sources and explain what they want to accomplish. The assistant saves a brief, applies relevant methods and presents a useful result or artifact. Exploration and archiving are valid alternatives. Internal phase results are tasks for the interface's reasoning engine, never a user checklist.

`goal_workflow.py` layers named collections and saved work over the original compiler. `collection_store.py` preserves additive source revisions and can copy an existing run without changing it. A brief stores the user's context separately from evidence. Each goal explicitly assesses extraction sufficiency; targeted source passes can extend knowledge. Builds bind source/IR revisions, brief, method, result, target and compiler fingerprint. Earlier builds remain reproducible after updates. Deterministic validation runs before a staged build becomes complete.

A coordinator now keeps per-project session state inside the home, separate from the installed skill, snapshots changed inputs automatically, validates complete checkpoints, and binds a reconciliation acknowledgement to their exact content. It assembles reviewed knowledge, validates proposals, binds displayed numbers to an IR/proposal revision, and creates or reuses checked exports. Review acknowledgements prove only that the agent signaled review; they do not establish semantic correctness. Explicit low-level tools remain available to contributors.

Capability reuse and comparisons resolve the selected/last-built option in the current corpus. Evaluation tasks/rubrics are frozen separately from exported skills. The same coordinator supports unrelated domains. Transcript-file and optional YouTube adapters supply raw bytes and metadata without IR coupling. YouTube acquisition uses network access only on requested processing (or explicit direct ingestion); no video/audio fallback exists. No natural-language parser in Python or external model call substitutes for the assistant's reasoning.

The value proposition is a maintained transformation between source material and useful actions. A transcript chat can answer excellent questions, but its method, scope limits, and source reconciliation are often implicit in a session. This compiler makes those choices durable and inspectable, then reuses them across tasks and assistants.

## What creates value

1. **Evidence-preserving transformation.** Every reusable unit retains exact source spans and attribution. Users can audit advice without searching a long conversation.
2. **Reconciliation.** Related and contradictory units remain linked. Export cannot quietly drop a recorded contradiction or prerequisite. Conflicts need an operating policy rather than a false consensus.
3. **Abstraction with disclosure.** Explicit source statements remain separate from inference and synthesized frameworks. Derivation explains how an abstraction was formed; no fake confidence number disguises that step.
4. **Proceduralization.** Capabilities specify inputs, branches, outputs, boundaries, examples, and checks. They aim to produce repeatable work on new inputs, not just summaries.
5. **Reusable assets.** A portable skill can be checked and used in a new session; the IR survives that target. Future knowledge packs, MCP tools, or agents can compile from the same representation.
6. **Evaluation and maintenance.** Held-out tasks, auditable citations, revision hashes, and deterministic failures make changes reviewable. Measured improvement, corpus quality, and reliable transformation workflows could become a defensible advantage. A folder format or prompt alone is not a moat.

## Architecture

Python owns parsing, canonical serialization, hashing, cross-reference checks, artifact assembly, and packaging. The user's assistant owns semantic extraction, reconciliation, capability discovery, and procedure design. There is no hidden paid API and no keyword extractor pretending to perform those semantic operations.

Source IDs bind relative filename and raw byte hash. Identical text from different filenames remains separate evidence; repeated content is not silently deduplicated. A corpus ID binds ordered source IDs and canonical document hashes, including metadata. IR hashes bind knowledge and coverage. Capabilities bind an IR hash. Package manifests bind every exported file except the manifest itself.

Sources and IR retain schema version `1.0`; new general outcomes use `1.1` and older builds remain readable. Incompatible versions fail closed. Arrays have deterministic order when assembled; canonical hashes use UTF-8 sorted-key JSON, while disk JSON is readable and indented. Source segment IDs are stable within an unchanged source snapshot. Editing a source creates a new identity rather than disguising changed evidence under an old ID.

Input snapshots and exports are staged and published only after validation. Source-level checkpoints enable resume without redoing complete sources. Assembly saves IR revisions and replaces the current IR atomically. Two writers should not edit the same run concurrently; distributed locking and merge resolution are outside the MVP.

Ordinary exports contain only the method, selected knowledge and relevant quotations. Closure checks preserve recorded prerequisites and contradictions. Export validators establish internal consistency, while private build validation links the export back to full originals and historical IR. Full private audit bundles and scoped portable exports are deliberately separate. Legacy full-corpus packages remain readable by the validator. Semantic review is still needed to detect private context paraphrased into a method.

## What this does not establish

Exact quotations and hashes establish identity and location, not truth, entailment, completeness, legality of reuse, or usefulness. The assistant can still misunderstand a source or design a weak capability. Instructions treat transcript content as untrusted data, but prompt wording is not a complete defense against adversarial content. Human review and realistic held-out evaluation remain part of quality assurance.

The demo includes unrelated domains to test the representation, plus an intentionally conflicting opinion to expose reconciliation behavior. It uses authored reference outputs, so it proves the deterministic pipeline can carry meaningful assets; it does not measure model extraction quality. The paired harness tests a separate hypothesis: whether reuse yields more actionable, faithful, traceable answers for comparable effort. Equal scores or higher upfront compilation costs are valid outcomes.

## Next investments after observing real use

The next highest-leverage feature is versioned, evidence-anchored interpretation corrections with regression cases: preserve the old interpretation, record the correction and rationale, create a new IR revision, identify affected builds, and verify the correction survives future compilation. Never overwrite raw evidence or attribute a correction to the source. Source changes must trigger reconsideration of dependent corrections. This is documented future work, not a new platform implemented here.

Use that quality loop to reveal which decomposition and selection contracts need stronger structure. Keep target/interface separation and backward compatibility explicit as those changes arrive. Additional ingestion integrations, exporters and hosted surfaces should follow demonstrated need rather than define the product. See the north star's twenty use cases and architectural review guardrails before extending scope.
