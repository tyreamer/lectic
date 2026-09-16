# Make saved expertise useful and visible

Use this guidance after discovery/builds and for “What did we save?”, “What can I do with it?”, “What else could this produce?”, or returning to old work. The user should not need to remember filenames, stages or capability terminology. The assistant is the interface; do not ask the user to operate these commands.

## Read before claiming readiness

Run `ec.py library --project PROJECT`, optionally with `--collection NAME`. This reads existing state without processing or modifying it. Explain the collection's real contents and distinguish:

- **Saved:** sources or captures retained; a saved URL does not supply its contents.
- **Ready to use:** an existing verified method and its previous result, with the actual input/output contract.
- **Can build next:** an evidence-supported opportunity, not a completed capability.
- **Saved earlier version:** usable historical material whose current applicability needs checking; never silently present it as updated.

Give readable names and clickable method/result links. Keep IDs internal. Report damaged or missing artifacts instead of labeling them ready. Archived collections and legacy packages remain visible. This command sees the current project, not all folders or host memory. If a known collection is absent, use a project location already supplied or ask where it was saved; do not immediately request the transcripts again or search unrelated private folders.

## Show concrete uses proactively

After completing the user's actual work, lead with the result. Then briefly show **what was saved**, **what they can do next**, and **how to use it again**. Do not stop at counts or a package path. Do not turn every intermediate extraction response into a discovery detour.

For “just save,” “don't process,” or capture-only instructions, give a short save receipt and availability state. Do not trigger extraction, a map or a new build. For explicitly completed knowledge preparation, explain that knowledge is saved and offer discovery as the next step. For source-only input with no storage restriction, continue the ordinary discovery flow without requiring a goal.

For discovery, completed builds and requests for more uses, run `ec.py guide --project PROJECT --collection NAME` (omit collection for the project library). It returns the verified library, a draft path and `use-guide.schema.json`. Write a private guide and save it using `guide --action save --draft PATH` with the same collection filter. Persist the suggestions so a fresh session can show them again using `guide --action show`. They live outside IR and exports.

Write one to three concrete next-use cards grounded in returned `references` and their source unit IDs. Each card states a job, what to provide, what comes back, why useful, a copyable natural-language request and meaningful limits. Separate ready applications from opportunities requiring a build. An example is an illustration, not a completed result or effectiveness evidence. If there are no supported choices, save an empty card list with an honest reason. Do not manufacture broad coaching, expertise or integrations.

Offer distinct applications rather than renaming the same output format. A review method might support a critique of a draft, a pre-publication check or a practice exercise, only where its actual scope and evidence allow. A creative method might support premise development, revision or structural analysis; don't promise an indistinguishable person or reuse source scripts as new work. These are possibilities to examine, not domain branches or default claims.

If a proposed use goes beyond a saved method, consult the collection's current map or explicitly discover further uses. Mark it **Can build next** and bind it to a supported opportunity. Do not silently broaden an existing method. Original evidence, exceptions and disagreements constrain every suggestion.

Recommend a starting use and explain why. Show the options before asking for a goal. Ask at most one useful question, such as “Would reviewing your current script or developing a new idea help more?” When intent/work is already supplied, proceed and leave `question` empty. Do not end every completed task with the same compulsory menu.

## Personalize from actual context

Use relevant facts the user stated, qualifications in saved personal context, or memory the host assistant has actually made available. The compiler neither reads a platform's memory API nor assumes memory is enabled. Record each used context item separately with an origin and source description. Never infer the user's job, preferences or endorsement merely from a saved corpus. Do not fetch private context from another application just to personalize.

For example, **if** the user actually said they make game reviews, suggest a supported review-script application and say why it fits. If that role was only a hypothesis, ask whether it fits; do not save it as a fact. Mark uncertain or possibly outdated supplied context `tentative`, use conditional language and let the user correct it. No host context available is a normal case: give useful general applications first.

Use only the minimum relevant context. Personal context and the guide remain private, never source evidence, IR units or exported skill content. A corrected context produces a new guide; do not edit source truth or silently rewrite previous guides. `context_ids` identify the context behind each personalized card. Reference validation does not prove the assistant's context attribution or source interpretation is true; review both before saving.

## Continue without making the user translate

“Let's do the second one” refers to the last guide actually shown. Call `guide --action select --select 2`, including `--guide-id` when referring to an earlier display. Use the saved card and reference, not a new ranking. Never apply guide numbers to a Capability Map or vice versa. If the guide is stale, explain what changed and show refreshed choices before interpreting a number.

Selection of a build opportunity enters the normal map/build pipeline. For a ready method, the result includes its actual method/result locations and the selected use. Read it, use work already supplied, or ask only for the input required by that use. In a named collection, create the ordinary private brief and proceed through `work`; reuse/adapt the saved method only within its evidence and applicability, preserving old outputs. A legacy package can be applied from its saved location; adopt its saved run into a named collection only when needed. Do not ask for source re-upload.

The selected application and its relevant personal context are stored in the build brief for a new opportunity. On resuming, read that context. After building the reusable method, continue the selected application if the user's actual input is available; otherwise ask for just that input. Do not restart discovery or declare the application completed merely because its supporting method now exists.

Keep capability choice and application distinct: “Build this reviewer” does not need a draft; “Review my draft” does. Current completion guidance must never imply that guide selection itself executed an application or produced a validated result.

## Example response shape

> Saved **Tech Review Methods** and a reusable **Product Fit Reviewer**. Your completed comparison is here: [result].
>
> You can use the saved method to check a review draft against its workload and tradeoff criteria. Give it your draft and actual test observations; get specific gaps and revision suggestions. It cannot fill in tests you haven't performed.
>
> Try: “Use my Product Fit Reviewer on this draft. Identify claims that need testing and suggest revisions.”

Use real saved names and evidence instead of copying this example. Mention additional build possibilities only when supported by the actual map. No confidence scores or claim of superiority from a saved artifact.
