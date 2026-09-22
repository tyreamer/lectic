# Internal operator guide — the assistant executes these steps

Resolve paths before invoking anything. `PYTHON` is the discovered interpreter, `SKILL_ROOT` the installed skill, and `PROJECT` the user's working folder. These are notation, not literal environment variables. Quote actual paths. Run from PROJECT and keep output internal.

```text
PYTHON "SKILL_ROOT/scripts/ec.py" compile "INPUT" --project "PROJECT"
PYTHON "SKILL_ROOT/scripts/ec.py" compile --project "PROJECT"
PYTHON "SKILL_ROOT/scripts/ec.py" compile --project "PROJECT" --intent discover
PYTHON "SKILL_ROOT/scripts/ec.py" compile --project "PROJECT" --intent build --select "2"
PYTHON "SKILL_ROOT/scripts/ec.py" compile --project "PROJECT" --intent build --build-all
PYTHON "SKILL_ROOT/scripts/ec.py" compile --project "PROJECT" --intent use
PYTHON "SKILL_ROOT/scripts/ec.py" compile --project "PROJECT" --intent compare
```

To adopt an existing run, use `--run RUN` without INPUT. The first positional argument always means transcript input. Optional metadata uses `--metadata PATH`. Relative paths resolve against PROJECT. New snapshots are named automatically under HOME/runs/; changed inputs create new snapshots. The active run, requested intent, and last-built choice persist in a per-project session file under HOME (`session.json` for a project-local legacy home). Omitting intent on resume preserves a pending build/use/compare request; explicit `--intent discover` changes that request.

The coordinator performs available deterministic work and returns a `phase`:

| Phase | Your next action |
| --- | --- |
| `needs_input` | Request the missing files/folder in ordinary language. |
| `extract` | Read the returned prompt/sources and write complete checkpoints at supplied paths. Repair listed bad checkpoints; preserve valid ones. Rerun with the original intent. |
| `repair_extraction` | Repair the listed evidence/relations issue and rerun. |
| `reconcile` | Review all checkpoints for scope, overlap, and conflict. Revise them, then rerun with `--reconciled` and the original intent. This attests your review of the current checkpoint bytes, not correctness; changes invalidate it. |
| `discover` | Read the prompt/IR and write or repair `capabilities.json` using the current returned `ir_hash`. Rerun. If no useful capability is supported, record a discovery assessment as described in that prompt instead of inventing one. |
| `choose` | Present the options in order. If strongest-capability selection was delegated, rerun with `--intent build --build-all`; if a supported option was specified, use its ID. Otherwise let the user choose. |
| `ready` | Explain what was built, link locations, and demonstrate a suitable example or invite a task. |
| `use` | Read the returned package/evidence and apply it now. The coordinator validates/retrieves the asset; you generate the answer. |
| `prepare_evaluation` | Follow the evaluation prompt; save genuine held-out tasks/rubric at returned locations, then rerun compare. |
| `evaluate` | Paired material is ready. Run isolated arms if available and authorized, otherwise hand over ready-to-paste prompts for fresh sessions. No user CLI work. |
| `no_supported_knowledge` / `no_supported_capabilities` | Explain why no useful capability is supported; identify needed material only when grounded in the user's goal. |

Do not stop because the next task needs reasoning or return the coordinator's JSON to the user. Repair authored data when possible; preserve snapshots and report only blockers you cannot resolve.

Numbers bind to a saved proposal list. If proposals change, the coordinator refreshes the list instead of silently reinterpreting an old number. Exact IDs/titles select current options. Resolve vague names like “photo critique” semantically against the actual supported scope.

New package revisions are separate; unchanged builds are validated/reused. Do not ask the user for a slug or export folder when the coordinator can choose it. Fix methods in capability records, not generated package files. Use an old package's bundled validator when inspecting a prior compiler build.
