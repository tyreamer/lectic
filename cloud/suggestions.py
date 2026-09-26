"""Pack-specific possibilities, cached separately from source ingestion."""
from .config import VERSION

GUIDANCE_VERSION = 3
FORMATS = ["Plan", "Checklist", "Lesson", "Review", "Proposal", "Your Idea"]


def discover(title, ir, model, user_context=""):
    known = {unit["unit_id"] for unit in ir["units"]}
    text = lambda maximum: {"type": "string", "minLength": 1, "maxLength": maximum}
    schema = {"type": "object", "properties": {
        "summary": text(400),
        "ideas": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
            "type": "object", "properties": {"title": text(200), "description": text(400),
                "format": {"type": "string", "enum": FORMATS}, "brief": text(1000),
                "unit_ids": {"type": "array", "minItems": 1, "maxItems": min(8,len(known)),
                             "items": {"type": "string", "enum": sorted(known)}}},
            "required": ["title", "description", "format", "brief", "unit_ids"], "additionalProperties": False}}},
        "required": ["summary", "ideas"], "additionalProperties": False}
    from jsonschema import validate, ValidationError
    error = ""
    for attempt in range(2):
        try:
            value = model.json(
                "Help a nontechnical person see how this context could be useful to them. Suggest exactly 3 different, concrete next steps. "
                "If they described their situation, tailor every idea to it without inventing personal facts. "
                "Use everyday language: a title of 3–7 words, a complete description sentence of at most 18 words, "
                "and a one-sentence summary of at most 24 words. Never cut off a sentence to meet a limit. "
                "Each idea must name a concrete use, "
                "not a generic format like 'make a plan'. Ground it in the provided unit IDs. Vary the uses: "
                "consider something to make, a problem to solve, a decision to explore, something to learn or share. "
                "Technical export formats live in a separate advanced menu. Do not suggest agent skills, MCP servers or technical tooling here. "
                "Supply a self-contained brief that asks Lectic to create an actual useful deliverable and includes the person's stated situation. "
                "For example ask for interview questions rather than telling Lectic to conduct real interviews. "
                "Do not invent circumstances or claim Lectic can perform actions outside this app. Keep jargon out of titles and "
                "descriptions. These are starting ideas, not the limits of what the pack can become.",
                {"title": title, "knowledge": ir, "person_context": user_context, "repair": error}, schema)
            validate(value, schema)
            for idea in value["ideas"]:
                if not set(idea["unit_ids"]) <= known: raise ValueError("An idea cites missing context.")
                if len(idea["title"].split()) > 9 or len(idea["description"].split()) > 22:
                    raise ValueError("Use a short title and a complete description of at most 18 words. Rewrite concisely; do not truncate.")
                idea["unit_ids"] = list(dict.fromkeys(idea["unit_ids"]))
            return {**value, "context": user_context, "guidance_version": GUIDANCE_VERSION, "model": model.last_model, "processing_version": VERSION}
        except (ValueError, ValidationError) as exc:
            error = str(exc)[:1000]
            if attempt: raise
