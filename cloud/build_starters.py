"""Build original MIT-licensed Startup Principles; reuse the other two verified packs."""
import os
from pathlib import Path
import shutil
import tempfile
from .config import ROOT
from . import compiler
from ec import ingest, validate_sources, write, fingerprint

MATERIAL = {
    "problem": [
        "Describe the person, the situation, and the costly problem before proposing a product. Keep observed behavior separate from your interpretation of it.",
        "Ask about the last time the problem happened. Record the workaround, the time or money spent, and what the person did next instead of asking whether they like your idea.",
        "A compliment is not a commitment. Define the action that would count as stronger evidence, such as a trial, a scheduled follow-up, or a purchase, before judging your experiment.",
    ],
    "experiment": [
        "Write the riskiest assumption as a statement that could be wrong. Design the smallest experiment that could change your decision and record the decision rule before running it.",
        "A failed test can be useful evidence. Compare what you predicted with what happened, list alternative explanations, and decide whether to change the problem, the offer, or the test.",
        "Build a narrow complete experience for one situation before expanding the feature set. Measure whether a person reaches the intended result without coaching.",
    ],
    "operating": [
        "Choose one near-term outcome and give it an owner. Keep a short record of the decision, its assumptions, and the next observation that would cause you to reconsider.",
        "Separate cash already committed from optional spending. Estimate the next experiment's cost and stop condition before committing funds; a forecast is an assumption, not a guarantee.",
        "Look for voluntary reuse after the first useful result. Ask what people returned to do and where they needed help; a signup count alone does not establish enduring value.",
    ],
}


def build():
    destination = ROOT / "fixtures/pilot"; destination.mkdir(exist_ok=True)
    for filename in ("debugging-starter.lectic", "customer-discovery.lectic"):
        shutil.copyfile(ROOT / "docs/packs" / filename, destination / filename)
    prior = os.environ.get("LECTIC_HOME")
    try:
        with tempfile.TemporaryDirectory(prefix="lectic-starters-") as temp:
            project = Path(temp); os.environ["LECTIC_HOME"] = str(project/"home")
            source = project/"sources"; source.mkdir()
            metadata = {}
            for name, paragraphs in MATERIAL.items():
                filename = name+".txt"
                (source/filename).write_text("\n\n".join(paragraphs)+"\n", encoding="utf-8")
                metadata[filename] = {"title": "Startup Principles: "+name.title(), "creator": "Lectic-authored teaching material", "caption_type": "synthetic"}
            write(project/"metadata.json", metadata); run = project/"run"
            ingest(source, run, project/"metadata.json")
            corpus, docs, _ = validate_sources(run)
            for sid, doc in docs.items():
                units = []
                for i, paragraph in enumerate(MATERIAL[Path(doc["filename"]).stem]):
                    segment = next(s for s in doc["segments"] if paragraph in s["text"])
                    units.append({"schema_version": "1.0", "unit_id": f"startup-{Path(doc['filename']).stem}-{i+1}", "type": "principle",
                        "status": "explicit", "title": paragraph.split(".")[0], "statement": paragraph,
                        "scope": "Lectic-authored teaching material under MIT; not empirical proof of business outcomes.", "derivation": "",
                        "evidence": [{"source_id": sid, "segment_id": segment["segment_id"], "quote": paragraph}],
                        "attribution": [{"source_id": sid, "name": doc["creator"]}], "relations": []})
                write(run/"units"/(sid+".json"), {"schema_version": "1.0", "corpus_id": corpus["corpus_id"], "source_id": sid,
                    "note": "Original teaching material authored by Lectic; no external expert attribution.", "units": units})
            compiler.Library(project).archive(adopt=run, name="Startup Principles")
            compiler.work(project=project, collection="Startup Principles", action="prepare", reconciled=True)
            compiler.build_pack(project, "Startup Principles", destination/"startup-principles.lectic", include_sources=True, version="1.0.0")
            shutil.copyfile(destination/"startup-principles.lectic", ROOT/"docs/packs/startup-principles.lectic")
    finally:
        if prior is None: os.environ.pop("LECTIC_HOME", None)
        else: os.environ["LECTIC_HOME"] = prior


if __name__ == "__main__": build()
