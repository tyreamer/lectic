# Know what you have and what to do with it

Lectic's interface is the assistant you already use. It should make saved expertise visible and suggest useful applications without requiring you to invent a goal or choose an artifact format.

In a project with saved material, say:

> Show me what Lectic has saved here. Explain what I can use now, show three concrete things I could do with it, and recommend where to start. Separate existing methods from things we could build next.

The assistant reads actual saved state, explains what exists and gives a small set of input → output examples. It does not start processing every saved link. If the original work lives in another project, open that project or supply its location; Lectic does not search all your folders or silently combine projects.

## What you should see

- **Saved material:** source documents, processed knowledge and captures that still need content.
- **Ready to use:** a saved, structurally checked method, its required input and its previous result.
- **Can build next:** a supported opportunity that needs compilation, clearly distinguished from an existing method.
- **Saved earlier version:** historical work kept intact, with a version check before treating it as current.

After completing a task, the assistant should explain the useful result first, name the method saved for reuse and give a concrete next-use request. It should not finish with only file paths, unit counts or a validation message. A method that passes structural checks has not thereby passed an effectiveness benchmark.

## Examples of guidance, not promises about an unseen corpus

| Saved expertise | Concrete next use | You provide → you get |
| --- | --- | --- |
| Workload-based tech review methods | Strengthen a review script | Draft and actual observations → unsupported claims, caveats and proposed revisions |
| The same review criteria | Plan missing tests | Claims and intended workloads → observations needed before recording a verdict |
| Absurd-procedure comedy methods | Develop a premise | Ordinary inconvenience → an original premise with a disproportionate rule |
| The same creative method | Outline or critique a scene | Premise or draft → escalating consequences or places the logic breaks |
| Focus/motion photography methods | Plan a retake | Observations and settings → diagnostic order and specific retake checks |

These examples use authored synthetic lessons in `fixtures/use-guidance/cases.json` and `fixtures/opportunities/`. They do not establish what the user's particular tech or comedy transcripts support, imitate a named person, or prove creative quality. The assistant must inspect actual evidence before making a recommendation. A new application beyond an existing method's scope remains a possible build until supported and compiled.

## Relevant personal context helps

If you have actually told the assistant you make game review videos, it can suggest applying supported review criteria to your scripts. It should explain that connection and retain limits: hardware workload methods do not establish game quality or supply unperformed benchmarks.

Lectic does not connect to a platform memory API. The assistant may use relevant context already exposed by its host, a user message or saved personal annotations. If no such context exists, it should still show useful general applications. It must not assume your job or endorsement from what you saved.

Personalized guides record the origin of used context separately from evidence. Uncertain or outdated context is tentative. Correcting it creates a new guide; it does not rewrite sources, IR or old builds. Guides are private local artifacts and are excluded from skill exports.

## Implementation and persistence

`scripts/library_guide.py` provides a read-only inventory and the separate use-guide coordinator. It validates saved build/package references, labels source/knowledge revision changes, includes archived collections and earlier compilation outputs, and reports unavailable or damaged artifacts without treating them as ready. Reading the inventory does not activate collections, start extraction or rewrite old results.

```text
.expertise-compiler/
  use-guides/
    drafts/BINDING_HASH.json
    guide-ID.json
    guide-ID.md
    index.json                 # history and last shown guide
```

`use-guide.schema.json` defines up to three cards, their saved method/opportunity reference, input/output, example prompt, limitations and source-unit basis. Each guide includes a snapshot binding and separately attributed personal context. Current inventory changes invalidate selection from an older guide until the assistant shows fresh choices. Old guides remain inspectable. Source-unit and reference checks cannot independently verify free-text usefulness, source entailment or the truth of an assistant's memory attribution.

The assistant operates:

```text
python scripts/ec.py library --project PROJECT
python scripts/ec.py guide --project PROJECT --collection NAME
python scripts/ec.py guide --project PROJECT --collection NAME --action save --draft DRAFT
python scripts/ec.py guide --project PROJECT --action show
python scripts/ec.py guide --project PROJECT --action select --select 2
```

Selection uses the last guide actually shown. Its numbering is independent of Capability Map numbering. A selected opportunity enters the existing build pipeline; selecting an existing method returns its saved reference and the chosen application. The assistant then uses work already supplied or asks for only the required input. Selection itself does not mean the new task is completed. New results still use the normal goal, evidence and validation flow.

Saved guides are interpretations of what a person could do next. They do not alter the durable Expertise IR or introduce new export targets, a global user profile, automatic memory retrieval or a separate chat UI.

## Live acceptance

1. Finish one real task. Without prompting for it, check that the assistant explains the saved method and a concrete way to reuse it.
2. Open a fresh session in the same project. Ask the opening prompt above. Check real artifact links, correct availability and no re-upload request.
3. Choose a shown use in ordinary language. Supply new work if required. Check it proceeds without asking you to translate the choice into a skill/agent format.
4. State a relevant role, then correct it. Check recommendations adjust, the basis is clear and source knowledge/old results stay unchanged.
5. Add a source and reopen an older guide. Check it flags the changed basis before interpreting an old number.

Measure whether the person can name what they have, choose a useful next task and actually complete it. Also compare the result and total effort against capable ordinary chat. Schema tests are not evidence that people understand the guidance or prefer the results.
