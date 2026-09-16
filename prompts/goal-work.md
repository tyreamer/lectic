# Internal operator guide: finish the goal

The assistant performs these operations. Paths below resolve against PROJECT unless prefixed SKILL_ROOT. Quote shell arguments; never interpolate source text into shell commands.

## Brief and collection

Write a UTF-8 JSON brief in PROJECT/.expertise-compiler/inbox using `schemas/brief.schema.json`. For every new goal include intent and intent_reason following [intents.md](intents.md), plus schema_version "1.0", objective, context, constraints, work {label,text}, desired_result and success_criteria. Legacy briefs without intent remain readable, but new work must use an explicit inferred intent. Preserve supplied text verbatim; when using other accessible work, record what was actually observed and its origin without inventing observations. The brief is private context, not source evidence. Users do not write JSON.

Start with absolute paths:

```text
python SKILL_ROOT/scripts/ec.py work --project PROJECT --input INPUT --name "Product Research" --brief BRIEF
```

The brief's intent selects the target automatically. Review/improve without work returns needs_work. No goal or archive intent: save the content and use [Capability Map discovery](opportunity-discovery.md), not a demand for a goal. The legacy CLI's needs_goal response remains for compatibility; the conversational interface should route unknown goals to discovery. “Just save for later”: --action save, no extraction. “Save these as NAME”: --action prepare, which extracts/reconciles broadly useful knowledge and ends at knowledge_saved without a brief, result or skill. Continue prepare with --reconciled only after reviewing extraction. Explore-only uses --action explore (delegates to map) and ends at capability_map. The older --target checklist remains for legacy runs; new checklist goals use intent plan.

After ingestion, omit --input, --name, --adopt and --brief on continuation calls. Continue `work --project PROJECT --collection "Product Research"`. Active brief and target survive interruptions. Do not repeat ingestion on each stage.

New task: save a new brief and pass --brief with existing --collection. Source additions: --input INPUT --collection NAME --action add; then resume work for the active goal if changed results were requested. Explain old/new result differences, not just source counts. Rebuild: --action rebuild. Identical inputs are idempotent; changed knowledge, brief, target or compiler creates a new build.

Use `ec.py library` and [guide-use.md](guide-use.md) for a returning user's overview of saved methods, actual results and possible next builds. `work --action list` remains the low-level collection summary. Adopt with `work --adopt OLD_RUN --name NAME --action save`; the old run is untouched. Read legacy `.expertise-compiler/session.json` to locate prior runs when needed, never erase them.

Inspect with --action inspect. Compare revisions with --action compare, optionally --before REV --after REV; otherwise compare the active source revision to its predecessor. For knowledge changes within one source revision, set --before and --after to that revision and use --before-knowledge HASH and optionally --after-knowledge HASH from saved build manifests or IR history. Translate IDs into readable titles. A missing knowledge comparison means extraction is unfinished, not that no knowledge changed.

Remove a source using --action remove --remove FILENAME (repeat for multiple sources); title or source ID also works when unambiguous. Originals stay in historical revisions, including when the active collection becomes empty. Replacement uses --action replace --input INPUT, matching filenames; metadata changes also create new revisions. Addition keeps both differently versioned files when they share a name. Removed evidence invalidates dependent units transitively. Valid partial units are saved in RUN/retained-drafts; inspect these before re-extracting affected sources. Restore supported units and reconsider their relations, never silently discard contradiction coverage. When the user asks what changed in the knowledge, finish pending preparation or the active goal before claiming that comparison is complete; distinguish pending extraction from an absence of changes.

--action archive marks the collection archived without deleting files; --action restore or explicit named use restores it. Listing includes archived collections so users can discover them later. Input paths still resolve against PROJECT, never the installation. Reading an old collection does not require source re-upload.

## Complete returned agent tasks

Returned run/draft/brief paths are authoritative. Read schemas from SKILL_ROOT/schemas. Stay in the work coordinator even when an older semantic guide mentions the legacy compile command.

1. **extract / repair_extraction:** follow [extract.md](extract.md). Use the brief to guide relevance but keep user context out of knowledge. Preserve existing units. Save complete source checkpoints in RUN/units; notes describe reviewed coverage and omissions.
2. **reconcile:** follow [reconcile.md](reconcile.md), then continue work with --reconciled. Read relevant methods/conflicts before acknowledging. Checkpoint changes invalidate this receipt.
3. **assess_coverage:** inspect IR against the brief. Write DRAFT/coverage.json per coverage-assessment schema, with returned brief_id/ir_hash. decision is reuse when sufficient, extend for a targeted pass; explain reason and unsupported requests. For extend provide real source_ids. Processing every source does not prove exhaustive extraction.
4. **extend_sources:** reread specified archived sources and extend checkpoints without deleting prior evidence. Reconcile, then rewrite coverage against the new IR hash. If rereading adds nothing, switch to reuse with honest unsupported limits. Coverage history and requested passes are preserved.
5. **design_method:** write DRAFT/method.json per goal-method schema: schema_version, returned brief_id/ir_hash, capability object. Read capability.schema.json and [compile-skill.md](compile-skill.md). Reuse a previous build's method when appropriate. Include required/contradictory evidence closure. Use synthetic examples, never private user work. Keep method source-specific and relevant to the goal.
6. **apply_method:** read actual work, goal and method. New intent-bearing briefs use the outcome schema and [intent-specific contracts](intents.md), not a disguised review or checklist. Write DRAFT/result.json with returned brief_id/ir_hash/method_hash and target. Deliver the requested work and retain evidence labels, disagreements and limits. Save improvements separately from originals. Old briefs without intent still use work-result schema. The coordinator returns outcome_schema and outcome_guidance to remove ambiguity.
7. **review_result:** inspect result, evidence and brief together for entailment, scope, inference labels, actionable changes, privacy and disagreements. Repair, rerun, and only then acknowledge with --reviewed. This is assistant review, not independent evaluation.
8. **complete:** saved artifacts exist and validate. When reopening, use `ec.py validate-build BUILD`. Lead with useful findings and clickable result/method links, then follow [guide-use.md](guide-use.md) to explain what is saved and suggest concrete next uses. Failed validation is not completion. Guidance follows the actual outcome; it never substitutes for doing the requested work.

No useful knowledge returns unsupported: explain the limitation; do not claim a compiled result. The archive remains available.

## Reuse, export and evaluation

Collections live at PROJECT/.expertise-compiler/collections/ID. collection.json maps source revisions, briefs and builds. Sources retain raw files, canonical documents, checkpoints and IR history. Builds retain brief, method, result and provenance bindings. requests contains resumable drafts, not completion artifacts. validation.json records reused/new/changed knowledge and unsupported requests.

New outcome builds save method.json and readable method.md with selected knowledge/evidence, but no SKILL.md or package. On explicit request, `work --action export` compiles that exact historical method/IR into a scoped Agent Skill in the local exports directory. Older builds may already contain a package. Export validation checks internal linkage; validate-build also verifies against historical private originals and full IR. Briefs, drafts and unrelated transcripts stay out of exports. Review semantic privacy too: schemas cannot detect private details paraphrased into a method. No publication or global installation is implied.

For comparisons follow [evaluate.md](evaluate.md) and [the protocol](../docs/EVALUATION.md). Supply the build brief as shared context to prepare_comparison, with its matching source/IR revision. Give both arms full source access and permission to retain context; conceal a frozen rubric. Track actual effort and leave unmeasured values empty.
