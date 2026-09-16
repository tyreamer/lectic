# Opportunity discovery fixtures

`cases.json` contains six unrelated or contrasting synthetic lessons and authored opportunity expectations. `tests/test_capability_maps.py` stages their source text, creates explicit evidence-linked extraction checkpoints, and submits authored discovery drafts through the same generic module. No domain-specific discovery branches exist. These fixtures test contracts, not whether a live assistant will independently extract or recommend the right things.

| Corpus | Supported examples | Input → transformation → output | Limits |
| --- | --- | --- | --- |
| Photography | Portrait Troubleshooting Guide; Portrait Critic | Portrait/settings → focus and motion checks → diagnostic order and retake plan | Does not support lighting or composition expertise |
| Sales | Discovery Call Reviewer; Discovery Preparation Guide | Call transcript → check concrete behavior and ownership → missing questions and follow-ups | Does not establish purchasing authority without confirmation |
| Architecture | Architecture Review Checklist; Access-Control Troubleshooting Guide | Access-control design → principal/action/resource checks → scoped issues and verification steps | Not a full security review |
| Business strategy | Market Decision Framework; Market Evidence Reviewer | Market hypotheses → compare behavioral commitments → conditional decision and missing evidence | Does not establish retention or market size |
| Reference | Observatory Reference Guide; Observatory Learning Guide | Question → retrieve bounded fictional facts → cited answer or learning material | Facts cannot justify procedural agents or reviewers |
| Conflicting experts | Evidence Threshold Comparison; Decision Policy Evaluator | Trial evidence → apply each expert's threshold separately → divergent conditional judgments | Must preserve disagreement, not average thresholds |
| Tech review | Workload Fit Reviewer; Review Test Planner | Draft and observations → check workload claims → caveats and missing tests | Does not supply new benchmarks or judge game quality |
| Comedy methods | Absurd Procedure Workshop; Scene Logic Reviewer | Premise/draft → inspect invented rules and consequences → original beats or revision advice | Synthetic high-level methods, not a named creator's material or a guarantee of humor |

The first four corpora contain a procedure, principle, example and limitation. The factual corpus deliberately does not. The conflicting corpus records a contradiction relation and requires it in both opportunities. Assessments have no confidence score. Source coverage is computed from exact linked units; fixture prose must not be mistaken for real expert material.

For a live test, use the [tester guide](../../docs/testing-guide.md) with actual authorized content. Assess relevance, faithfulness, ranking and reuse with humans. Structural validation cannot detect every unsupported promise in free text.
