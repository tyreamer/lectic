---
title: WayKit example gallery
description: Five reproducible journeys from trusted source material to reusable, evidence-backed expertise
---

## Five reusable expertise journeys

These examples use small authored fixtures in this repository so you can run them offline and inspect every source sentence. The situations are realistic, but the fixture material is synthetic teaching data, not a claim that WayKit evaluated a live expert or measured model quality.

From a repository checkout, install WayKit and connect an assistant once:

```bash
python -m pip install -e .
waykit setup --yes
```

Each example follows the same loop:

```text
INPUT -> WAYKIT -> ARTIFACT -> REAL USE
# (formerly: INPUT -> LECTIC -> ARTIFACT -> REAL USE)
```

## Learn from an expert: diagnose handheld blur

### Input

The timed tutorial in `fixtures/photography/photography.vtt` separates camera shake from missed focus. It recommends inspecting a test photo before changing settings, explains the light tradeoff from a faster shutter, and warns that shutter speed cannot repair missed focus.

### WayKit

```bash
waykit start fixtures/photography --name "Handheld Photography" --goal "diagnose blur and plan the next test" --yes
```

Open your connected assistant and send the exact prompt printed by `waykit start`. The assistant prepares reusable checks while WayKit retains the tutorial timestamps and quotes.

### Artifact

The collection can support a diagnostic method with three bounded steps: inspect the blur, test camera shake with the stated exposure tradeoff, then check focus before drawing a conclusion. Generate its public page after preparation:

```bash
waykit share-artifact "Handheld Photography"
```

### Real use

> Use my Handheld Photography collection. A stationary storefront is blurry, and part of the sign is sharp. What should I test next, and what tradeoff should I expect?

This applies the tutorial to a new photograph instead of summarizing the lesson again.

## Developer: review an access-control design

### Input

`fixtures/universal/architecture/source.txt` contains two architecture rules: define the principal, resource, and action before choosing credentials, then test expiration and revocation as separate failure cases.

### WayKit

```bash
waykit start fixtures/universal/architecture --name "Access Control Review" --goal "review authorization designs and test plans" --yes
```

Ask your connected assistant to prepare the collection using the prompt WayKit prints.

### Artifact

The reusable expertise is a narrow architecture review, not a generic security certification. It can check whether an authorization proposal identifies the decision being made and whether its failure tests distinguish expiry from revocation.

### Real use

> Use my Access Control Review collection on this design: a service account presents a token to update invoices. The test plan checks only an expired token. What is underspecified, and which separate test is missing?

When the architecture notes change, refresh the same maintained collection:

```bash
waykit refresh "Access Control Review" --from fixtures/universal/architecture
waykit diff "Access Control Review"
```

## Student: turn learning science notes into a study method

### Input

`fixtures/universal/education/source.txt` says to ask learners to retrieve an idea before showing the explanation, then use the learner's error to choose the next example.

### WayKit

```bash
waykit start fixtures/universal/education --name "Active Recall Study" --goal "plan study sessions that adapt to mistakes" --yes
```

The assistant prepares the source-backed procedure without adding unsupported claims about grades, memory duration, or a specific subject.

### Artifact

The resulting study method can order a session: attempt retrieval, inspect the error, select a targeted example, and try retrieval again. The original notes remain available as evidence.

### Real use

> Use my Active Recall Study collection to plan 20 minutes on photosynthesis. I keep confusing where the light-dependent reactions happen. Do not show the answer before the first retrieval attempt.

The new task applies the saved teaching method to biology material that was not in the source.

## Professional research: preserve disagreement in a trial decision

### Input

`fixtures/opportunities/conflicting/source.txt` records two explicit thresholds for a small reversible trial. One expert would proceed after one confirmed customer commitment; the other requires three. The source limits both thresholds to a trial, not a full launch.

### WayKit

```bash
waykit start fixtures/opportunities/conflicting --name "Trial Decision Thresholds" --goal "compare recommendations without averaging away disagreement" --yes
```

### Artifact

The collection preserves both rules, their conflict, and their shared scope. It should not manufacture a compromise threshold or turn a small-trial rule into launch advice.

### Real use

> Use my Trial Decision Thresholds collection. We have two confirmed commitments and can run a two-week reversible pilot. Show what each expert would recommend and what this evidence cannot decide.

The value is traceable comparison on a new decision, not a blended summary.

## Personal playbook: run controlled debugging experiments

### Input

`fixtures/debugging/debugging.srt` is a short timed lesson: reproduce the smallest failure, change one suspected cause at a time, revert ineffective changes, and retain both the original reproducer and a nearby boundary test.

### WayKit

```bash
waykit start fixtures/debugging --name "Debugging Playbook" --goal "review bug-fix plans before I edit code" --yes
```

### Artifact

After preparation, the playbook can review a proposed debugging approach against the same evidence-backed sequence every time. Package it for another WayKit user or generate a read-only page:

```bash
waykit pack "Debugging Playbook"
waykit share-artifact "Debugging Playbook" --no-quotes
```

### Real use

> Use my Debugging Playbook to review this plan: change the parser and delimiter settings together, then ship after one sample passes.

The artifact matters because the method can be applied again to a different parser, service, or failing input while its limits and evidence remain visible.

## What the examples prove

The fixtures and automated tests prove storage, source identity, evidence links, revision history, packaging, and deterministic workflow boundaries. They do not prove that every connected assistant will produce the same prose or that the synthetic methods are effective in the real world. Use the [live acceptance protocol](ASSISTANT-FLOWS.md) for model behavior and quality checks.