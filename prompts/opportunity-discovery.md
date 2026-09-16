# Discover what this collection can become

Use when content arrives without a goal (unless the user only wants storage), or asks what to build, what a collection is capable of, or what to build first. Discovery is a derived interpretation of expertise, not new source truth. Never write opportunities into IR. Don't require users to choose intent labels or formats.

## Operate and resume

Archive new inputs with `ec.py work --input INPUT --name NAME --action save`, then run `ec.py map --collection NAME`. Handle returned extraction and reconciliation tasks yourself; resume `map`, passing `--reconciled` only after reviewing the checkpoints. If nothing reusable is supported, explain that honestly. The map command reuses a current map or returns a bound discovery task. Follow its schema and save the draft at the returned path, then rerun `map --draft PATH`. An interrupted draft survives reload. Use `--regenerate` to request a fresh assessment of unchanged expertise; subsequent submission uses `--draft`, without `--regenerate`.

Read all current IR units, scopes, evidence, coverage notes and relationships. Inspect archived segments where interpretation is uncertain. If coverage is inadequate, extend extraction and reconcile before mapping. A small or incomplete corpus does not justify broad expert claims. Source coverage is computed from cited units, not invented in prose. Numeric counts are evidence counts, never confidence.

## Assess before recommending

Inspect all ten categories internally: CREATE, REVIEW, IMPROVE, DECIDE, PLAN, DO, LEARN, REFERENCE, AUTOMATE, EVALUATE. Save one reason and relevant evidence list per category even when unsupported. Do not force a recommendation for each.

Author at most eight distinct candidates, normally three to five supported opportunities plus only gaps worth explaining. One or zero supported opportunities is valid. Avoid duplicate ideas dressed in different artifact names. Stable opportunity IDs identify the same job across revisions; inspect the previous map before assigning them. Preserve IDs when the job remains the same, not when its meaning changes.

For each candidate specify input → transformation → output; problem solved; evidence IDs and why those passages support that specific job; applicable boundaries and conditions; all recorded contradictions touching selected units, including opposing units outside the selection; how disagreements will remain visible; and plausible delivery forms.

Grounding roles cite rules, procedures, criteria, examples/counterexamples and conditions. Missing examples or exceptions are real gaps; don't relabel a fact as a procedure or treat any nonempty scope as sufficient conditions. Deterministic guards check types and references, not meaning. Fact-heavy material may support source-backed reference and bounded lessons but not a reliable reviewer, decision agent or procedural coach. A title like “agent” does not supply missing evidence.

Assess support as `strong`, `supported`, or `weak`. Strong actionable opportunities require relevant examples and applicability conditions as well as rules or criteria. One source can support a narrow useful method; repeated sources do not establish independent agreement. Note common attribution and caption limitations when material.

Provide qualitative `high`/`medium`/`low` judgments with reasons for repeat usefulness, actionability, available judgment and saved repeated work. State whether value beyond Q&A is `distinct`, `modest` or `none`, and explain the actual difference. Honest modest value is acceptable for reference. Do not claim measured savings or superiority. Ranking is lexicographic: support, reuse, actionability, saved work, judgment, differentiation; stable ID breaks ties. Write a ranking reason consistent with those factors.

Targets have a readable label and a delivery mode: `text` (a usable method, reviewer instructions, lesson, framework, SOP or rubric), `skill` (existing optional Agent Skills exporter), or `future` (unimplemented runtime/integration). Agent, Workflow, Coach, Reviewer, Tutor, Framework, SOP, Eval Suite, Knowledge Pack and Custom are examples, not an exhaustive enum. Never label an autonomous agent, persistent coach or executable eval suite as shipped merely because we can draft its instructions. Only mention future formats when useful, clearly marked. Supported recommendations need a currently deliverable form. Weak candidates explain gaps and cannot be selected for building.

Before submitting, review the entire draft against source meaning and the criteria above. Set the assistant semantic-review acknowledgement honestly. This is not independent effectiveness testing.

## Show and build

Use the saved map's recommended order (up to five) when showing the map itself. Lead with useful names, then concise give/get, why supported, repeat-use value and important limits. Formats are secondary. Follow [guide-use.md](guide-use.md) to save up to three concrete applications of those opportunities, optionally tailored to actual user context. Label them as possible builds, not already saved capabilities. A use guide has its own saved numbering; never interpret its numbers as map indices. Show useful possibilities before asking which would help. Never announce a fixed number of strong opportunities if support is mixed or absent.

“Build #2” uses the last shown map, not a new ranking. Call `ec.py map --collection NAME --action select --select 2` (title or ID also works). When referring to a specific earlier display pass its `--map-id`. The saved opportunity becomes a private CREATE brief for building the reusable capability itself; the opportunity's future use categories remain in context. Continue returned normal `work` tasks to a validated result. Do not ask for an application draft just to build a reviewer. Do not rediscover the idea, omit its boundaries, or stop after writing a pitch. Use the selected evidence, extend extraction only when needed, and produce a ready-to-use method with a synthetic worked example. Export a skill only when requested; no asset-type question is necessary.

If a selected map is stale, regenerate and show the revised opportunities before interpreting a number. A newer map must never silently change what an earlier “#2” means. `map --action inspect --map-id ID` reads old maps; `--action list` lists history. `map --action compare --before OLD --map-id NEW` reports new, strengthened, weakened/removed, newly supported, changed-evidence and conflict-affected entries. Inspect both maps to explain the evidence behind changes in plain language. Don't imply that a changed support judgment is a measured improvement.
