# Develop the skill

The installed SKILL.md is the current conversational interface to the core compiler; the CLI is another interface. Neither defines the product. Follow [NORTH_STAR.md](../NORTH_STAR.md) and the [current boundary map](../DESIGN.md) when extending the code. The assistant operates utilities and supplies reasoning while the user supplies content and build intent. Keep target/runtime details out of canonical expertise records.

## Local checks

Python 3.10+ is the only runtime requirement. From a checkout:

```text
python -m unittest discover -s tests -v
python scripts/demo.py --output workspace/demo-current
python scripts/evaluate.py prepare --demo workspace/demo-current
```

The suite retains evidence/schema/hash/package failures and adds installed-skill execution from another working directory, spaces in paths, resume/selection binding, reconciliation invalidation, source changes, independent domains, and comparison preparation. Semantic fixture checkpoints are authored oracle data, not a claim that these tests ran an AI assistant. [Live conversational acceptance protocol](ASSISTANT-FLOWS.md).

## Clean local install

An assistant can download/review a checkout, then install a clean copy using:

```text
python scripts/install_skill.py --dest /personal/skills/expertise-compiler
```

Resolve the platform's destination first: Codex's installed `$skill-installer` chooses its personal directory; Claude Code uses `~/.claude/skills/expertise-compiler`. The copy helper accepts an explicit path and never downloads or silently overwrites a differing installation. It includes runtime resources and fixtures, but no `.git`, caches, or user work. Tests install to temporary directories; they do not change real user configuration.

For Codex's bundled GitHub installer, use repository `tyreamer/lectic`, path `.`, and explicit name `expertise-compiler`. Follow the installed helper's actual syntax. For example, where that helper is present: `install-skill-from-github.py --repo tyreamer/lectic --path . --name expertise-compiler`. This is internal installation machinery; the README gives a chat request instead.

## Structure

- `SKILL.md`, `agents/openai.yaml`: discovery, intent routing, conversation contract.
- `scripts/workflow.py`: saved project state and deterministic orchestration; returns agent tasks at semantic boundaries.
- `scripts/goal_workflow.py`, `scripts/collection_store.py`: goal briefs, named archives, coverage reassessment, saved reviews/checklists and immutable build validation.
- `scripts/scoped_export.py`: selected method/evidence export, with full originals retained privately.
- `scripts/outcomes.py`: the eight domain-independent intent contracts and general result rendering. Natural-language inference belongs to the host assistant and is documented in prompts/intents.md.
- `scripts/ec.py`: preserved ingestion, normalization, IR assembly, integrity checks, and portable export.
- `scripts/ingestors/`: transcript file adapter and an explicit unavailable YouTube boundary. Adapters produce original bytes/metadata, not knowledge units.
- `prompts/`: detailed reasoning and operator instructions, loaded as needed.
- `schemas/`: versioned durable artifact contracts. Regenerate from `scripts/build_schemas.py` when intentionally changing them.
- `fixtures/flows/`: domain-specific held-out cases and scripted conversation contracts.

Project state lives in `.expertise-compiler/`, outside the installed skill. Add that directory to the consuming project's ignore rules before publishing its project; the compiler does not silently modify unrelated Git settings. This repository already ignores it.

`tests/test_goals.py` covers goal/no-goal/archive paths, actual saved synthetic reviews in two domains, fresh-process collection reuse, checklist output, another source pass, additive source dependencies, private export boundaries, adoption, tampering, installation and fair evaluation context. It replays authored semantic data at the assistant boundary; it is not a live assistant effectiveness test.

`tests/test_universal.py` uses six unrelated synthetic corpora under fixtures/universal and all eight intents through the same coordinator. It verifies useful section contracts, explicit intent/reason persistence, no automatic skill package, fresh-process reuse, targeted extraction, source replacement/removal (including an empty active collection), relationship invalidation, source/knowledge comparisons, archive/restore, prepare-only knowledge and historical validation. The fixture intent labels and prose are authored expectations, not a simulated model-inference success. The live protocol tests that separate boundary.

## Validation limits

`tests/test_capture.py` covers immutable capture import and retries, attachment hashes/path boundaries, annotations, multiple collection memberships with shared underlying files, source-local extraction reuse, fresh installed CLI operation, and two unrelated capture-to-build workflows. Authored outcome fixtures expose unavailable links and missing details; they do not prove live assistant behavior. The iPhone design needs real-device testing. `capture_store.py` adds no retrieval or model dependency, and `Library.attach_shared` preserves existing snapshot/validation contracts.

`tests/test_capability_maps.py` adds generic opportunity contracts across six synthetic corpora: grounded DO/REVIEW, factual-only rejection, disagreement preservation, ranking, complete internal category assessment, fresh-process reuse, immutable IR/maps, stale selection, source additions/removal, map comparison, draft resume, tampering and direct selection through a completed build. It uses authored semantic checkpoints/drafts, not a live model. New schemas are generated by `scripts/build_schemas.py`. Discovery prompts and the saved map binding must evolve together; increment `DISCOVERY_VERSION` when changing the assessment contract.

Schema/evidence checks prove structure and reference identity, not truth, entailment, completeness, or quality. Reconciliation receipts record that the assistant explicitly acknowledged reviewing current checkpoints; they are not a semantic validator. Manifest hashes detect changes, not malicious re-signing. The implementation uses no external model calls.

Generated package rendering is retained for compatibility; its internal validation instruction is for the agent to execute. User-facing delivery comes from the compiler skill, which must not hand those instructions back as homework. Old packages retain their bundled validators. [CLI details](CLI.md) · [Architecture](../DESIGN.md).
