# Lectic: product north star

Lectic takes trusted human content and compiles its useful expertise into a durable, structured, evidence-preserving representation. People building with AI can select and rebuild that expertise toward different goals, capabilities and runtimes.

The assistant interface should actively explain what has been saved and suggest concrete, supported applications before asking users to invent a goal. A readable library and private next-use guides expose the value of durable expertise. Relevant context actually available from the user or host may personalize those guides; it is not source truth, a global identity profile or an assumed connection to platform memory. These presentation artifacts remain separate from IR and portable build targets.

**Delphi digitizes the expert. Lectic compiles the expertise.**

This is product-direction shorthand, not a verified comparison of another company's features. The architectural distinction is: **digital person platforms package the person; Lectic packages reusable pieces of the expertise.** Recreating a person is neither required nor the default.

## What the product is for

The primary users are people building with AI: AI engineers, developers, architects, consultants, agencies, creators building AI products, internal AI teams, technical operators and advanced individuals assembling custom workflows. Consumers can also use the resulting expertise directly.

The product is not primarily a document chatbot, a digital-person or fan-conversation destination, a competitor defined by persona replication, a Codex skill product, a YouTube-to-SKILL.md generator, or a knowledge base limited to one output. Chat, transcript ingestion and skill installation are useful interfaces or implementation choices, not its identity.

## The durable asset

Compiled expertise may include knowledge, concepts, reasoning patterns, mental models, procedures, heuristics, decision rules, conditions and exceptions, communication patterns, vocabulary tendencies, creative methods, examples and counterexamples, disagreements, evaluation criteria, style characteristics and their source evidence.

These dimensions can be selected independently. Knowledge does not imply personality; communication style does not imply opinions; reasoning patterns do not require impersonation. Observed patterns must remain distinct from interpretations of those patterns and from newly synthesized methods. A source-backed statement is not automatically true.

**One corpus can be compiled multiple ways for different goals without re-ingesting or destroying the original expertise representation.**

The corpus can emerge during normal life. A provider-independent capture layer sits before sources and collections: encounter useful material → capture immediately → optional personal context → Inbox or multiple collections → process when useful → durable expertise → Capability Map or goal → build → reuse. A user need not prepare a corpus in advance. Capture exists to feed reusable expertise, not to reposition the product as a bookmarking destination.

Capture records, source content, personal reasons for saving, and compiled methods are distinct records. Saving does not imply retrieval, understanding, agreement, endorsement or policy authority. One canonical source can have several collection memberships. Saving should remain cheap; never repeatedly pay to understand the same available content unnecessarily. Reuse verified representations and perform incremental work when a goal needs it, not on every share.

Deferred acquisition fills the gap between saving a link and possessing usable source content. YouTube caption retrieval is the first supported linked-source adapter, invoked when a user requests processing or useful work. Its cached original bytes feed the existing source contracts; retrieval never substitutes for extraction, reconciliation or evaluation. Other platforms can add adapters without changing the Expertise IR or making ingestion the product's identity.

The first capture interface is an iPhone Shortcut using a synced folder; iCloud is an adapter, not a core dependency. Future share extensions, web clippers, email, Android or API adapters can implement the same contract. No native app, hosted account system or background processing service is required for this proof. Explicit IDs and relationships support future traversal; a graph database is an option only if demonstrated relational complexity justifies it.

Users do not need to invent a goal first. Capability Maps provide a core exploration experience: derive the strongest supported opportunities from saved expertise, explain input → transformation → output and limits, then carry the selected opportunity directly into a build. Maps are versioned interpretations, separate from source truth and regeneratable without changing IR. A known goal bypasses the map; archive-only requests still preserve content without forcing discovery.

Selection creates a build-specific view of expertise, not a destructive filter on the collection. If a new goal needs something not extracted before, revisit archived sources and extend the IR with a new revision. Do not assume the first extraction was exhaustive.

For example, the same collection of 50 expert videos could independently support:

1. A decision framework using reasoning but none of the experts' personality.
2. A questioning skill based only on interview techniques.
3. A writing-style guide using language tendencies while excluding opinions.
4. A reviewer applying evaluation criteria.
5. A teaching coach based on instructional methods.
6. An evaluation suite testing whether another AI follows the extracted principles.

These are independent builds from shared sources and expertise, not successive conversions that replace one another. This example describes the intended architecture, not a claim that all six exporters exist today.

## Compilation model

```text
DISCOVER CONTENT DURING NORMAL LIFE
        ↓
CAPTURE + OPTIONAL PERSONAL CONTEXT
        ↓
SOURCE COLLECTION
        ↓
DURABLE EXPERTISE IR
        ↓
CAPABILITY MAP / USER BUILD INTENT
        ↓
SELECT / EXTEND RELEVANT EXPERTISE
        ↓
COMPILED METHOD / CAPABILITY
        ↓
TARGET ARTIFACT
        ↓
VALIDATE / EVALUATE
        ↓
PORTABLE OUTPUT
```

Build intent includes the goal, context, requested result, relevant dimensions to include, dimensions to exclude, and behavior to assess. A user can name an extraction focus, an exclusion, or a custom desired capability:

> Extract only how these people make decisions.

> Use their knowledge but none of their personality.

> Build a reviewer that applies these five experts' positioning principles, preserves where they disagree, and does not imitate any of them.

The compiler should interpret these intentions rather than require a fixed artifact menu. Intent classes describe the work to accomplish; targets describe representations or runtimes. Neither is the taxonomy of expertise itself. Today's eight intent classes and section types are implemented conventions, not an exhaustive ontology or permanent restriction on custom builds.

## Targets are extensible

Potential targets include a knowledge collection or pack, agent skill, agent, workflow, reviewer, coach, tutor, decision framework, SOP, troubleshooting capability, evaluator, evaluation suite, creative-method profile, reasoning profile, communication-style profile, portable prompt/config package, future MCP/API representation and user-defined capabilities.

This is an open set of examples, not a backlog commitment to build every exporter or a list of separate products. A new target should consume a selected, versioned view of expertise and declare its own validation and runtime requirements. It should not require provider-specific fields in the canonical source or IR models. Portability means preserving the representation and its dependencies while making runtime assumptions explicit, not promising execution in every environment.

## Canonical responsibilities

The following is a conceptual architecture, not a claim that these directories or all modules exist today:

```text
capture-layer/
  immutable captures, optional annotations
  Inbox, source membership, processing state
  generic adapter contract

expertise-core/
  sources, collections, expertise IR
  extraction / reconciliation
  goals / build intent, compilation
  provenance, versioning, validation, evaluation

targets/
  skill, agent, workflow, reviewer, coach
  eval, knowledge-pack, custom, future targets

interfaces/
  iPhone Shortcut / synced-folder capture adapter
  Codex skill, Claude Code skill, CLI
  future desktop, web, API, MCP
```

Interfaces gather intent, obtain authorized inputs, supply or coordinate reasoning, invoke core operations and present results. Targets render or adapt compiled capabilities. The core owns durable records, selection, evidence, versions and validation contracts. Core schemas must remain independent of AI provider, assistant, output target and runtime. Dependency direction should flow from interfaces and targets toward core contracts; core records must not require a particular installed skill.

The installed Codex/Claude skill is one interface to the compiler. It currently bundles utilities for convenient local execution. That packaging does not define the core architecture. See [DESIGN.md](DESIGN.md) for the actual code mapping and remaining coupling.

## Twenty use cases that preserve the breadth

These are architecture checks, not twenty products or hard-coded workflows:

1. Build reusable AI expertise from favorite experts.
2. Preserve company tribal knowledge.
3. Learn from curated corpora.
4. Review real work using trusted methods.
5. Turn courses into ongoing AI coaches.
6. Provide decision support from trusted thinkers.
7. Generate reusable agent skills.
8. Process internal training libraries.
9. Create creator-owned knowledge products.
10. Build personal knowledge operating systems.
11. Compile sales methodologies.
12. Build technical troubleshooting capabilities.
13. Generate SOPs from demonstrations and training.
14. Build role-onboarding systems.
15. Compile creative and style methods.
16. Synthesize and reconcile multiple experts.
17. Build best-practice evaluators.
18. Turn meeting archives into organizational capability.
19. Extract persona, reasoning and communication components independently.
20. Generate domain-specific AI evaluation suites.

## Where the value must compound

Ingestion and asset generation are necessary plumbing, not sufficient differentiation. The harder value is faithful decomposition, exact source evidence, explicit separation of source statements and compiler inference, conditions and exceptions, preserved disagreements, user correction, reuse across targets, versioning and evaluation of whether a capability behaves as intended.

Keep attribution, derivations, explicit/inferred/synthesized status, limits and dissent through every transformation. Do not invent numerical confidence or collapse disagreement into consensus. Separate structural validity, evidence linkage, semantic review and observed effectiveness. Evidence that an artifact is well formed does not prove that its behavior is right.

Private source archives retain full originals and audit records. Outputs and exports carry only what is relevant to their use and provenance, respecting sharing intent. Source attribution does not grant redistribution rights. No automatic publishing or global installation follows from compilation.

## Next major quality direction: correct once, improve future builds

A user should be able to correct an interpretation once and have future builds and tests reflect that correction. The highest-leverage next technical feature is **versioned, evidence-anchored interpretation corrections with regression cases**.

The intended small first slice records a correction against a unit and source revision, preserves the prior interpretation and rationale, produces a new knowledge revision, identifies affected builds, and carries a concrete regression case into subsequent validation/evaluation. It must not rewrite raw sources or present a user correction as an original source statement. Changed source evidence should trigger reconsideration rather than blindly reapplying an old correction. Conflicting corrections need explicit scope and history.

This feature is not implemented by this alignment pass. It is a quality loop within the compiler, not a correction dashboard, hosted platform, or broad evaluation product.

## Change-review guardrails

For future architectural changes, reviewers should ask:

- Can the same collection and IR still serve independent builds, including different inclusion/exclusion choices?
- Are new provider/runtime/target details isolated from canonical source and expertise records?
- Is an intent class being mistaken for a fixed list of all possible target artifacts?
- Do selected views and corrections preserve originals, prior interpretations and independent build history?
- Can we trace behavior to source evidence and distinguish inference, synthesis, user context and original work?
- What test would reveal that the compiled capability does not behave as intended?
- Does this strengthen expertise compilation for AI builders, or drift toward a digital-person destination or ingestion-only utility?

Do not add hosted services, accounts, marketplace, billing, MCP, agent teams or a large catalog of interfaces/targets simply to illustrate this architecture. Extend real boundaries incrementally, keep older artifacts readable, and label future direction separately from implemented capability.
