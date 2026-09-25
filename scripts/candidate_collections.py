"""Intelligent candidate collection matching for incoming source material.

When a user shares a link, video, pasted text, transcript, or file, Lectic
must always ask which collection to add it to before assuming or creating a new one.
This module inspects existing collections in the library, extracts topic, creator,
and keyword signatures, and scores candidate collections for relevance so the
assistant can present intelligent suggestions alongside all existing collections.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from collection_store import Library
from ec import read, safe_child

STOPWORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are',
    'aren', 'arent', 'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between',
    'both', 'but', 'by', 'can', 'cant', 'cannot', 'could', 'couldnt', 'did', 'didn', 'didnt',
    'do', 'does', 'doesn', 'doesnt', 'doing', 'dont', 'down', 'during', 'each', 'few', 'for',
    'from', 'further', 'had', 'hadn', 'hadnt', 'has', 'hasn', 'hasnt', 'have', 'haven', 'havent',
    'having', 'he', 'hed', 'hell', 'hes', 'her', 'here', 'heres', 'hers', 'herself', 'him',
    'himself', 'his', 'how', 'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in', 'into', 'is',
    'isn', 'isnt', 'it', 'its', 'itself', 'lets', 'me', 'more', 'most', 'mustn', 'my', 'myself',
    'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours',
    'ourselves', 'out', 'over', 'own', 'same', 'shant', 'she', 'shed', 'shell', 'shes', 'should',
    'shouldnt', 'so', 'some', 'such', 'than', 'that', 'thats', 'the', 'their', 'theirs', 'them',
    'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd', 'theyll', 'theyre', 'theyve',
    'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasn', 'wasnt',
    'we', 'wed', 'well', 'were', 'werent', 'what', 'whats', 'when', 'whens', 'where', 'wheres',
    'which', 'while', 'who', 'whos', 'whom', 'why', 'whys', 'with', 'wont', 'would', 'wouldnt',
    'you', 'youd', 'youll', 'youre', 'youve', 'your', 'yours', 'yourself', 'yourselves',
    'http', 'https', 'www', 'youtube', 'com', 'watch', 'video', 'transcript', 'channel',
    'playlist', 'v', 'sources', 'source', 'collection', 'notes', 'file', 'files', 'text'
}


def _tokenize(text: str) -> list[str]:
    """Extract lowercased alphanumeric word tokens filtering out common stop words."""
    if not text:
        return []
    raw = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [w for w in raw if len(w) >= 2 and w not in STOPWORDS]


def _clean_str(text: str) -> str:
    """Normalize whitespace and lowercasing for substring checks."""
    return ' '.join(re.findall(r'[a-zA-Z0-9]+', (text or '').lower()))


def find_candidate_collections(project='.', *, url='', text='', title='', files=(), note='') -> dict[str, Any]:
    """Match incoming source material against existing collections.

    Returns:
      has_collections: bool
      total_collections: int
      candidates: list of candidate dicts ranked by score descending
      all_collections: list of all existing collections
      suggested_action: 'ask_with_candidates' | 'ask_all_collections' | 'no_collections'
      prompt_guidance: instruction for formulating the question to the user
    """
    library = Library(project)
    entries = library.index.get('collections', [])
    if not entries:
        return {
            'has_collections': False,
            'total_collections': 0,
            'candidates': [],
            'all_collections': [],
            'suggested_action': 'no_collections',
            'prompt_guidance': 'There are no existing collections yet. Propose creating the first collection for this material, suggesting a clear name based on the content.',
        }

    # Aggregate incoming content for feature extraction
    incoming_parts = [title or '', url or '', (text or '')[:3000], note or '']
    for f in (files or ()):
        incoming_parts.append(Path(f).stem.replace('-', ' ').replace('_', ' '))
    full_incoming_raw = ' '.join(incoming_parts)
    incoming_tokens = set(_tokenize(full_incoming_raw))
    clean_incoming = _clean_str(full_incoming_raw)

    collection_scores = []
    all_summary = []

    for entry in entries:
        coll_id = entry['collection_id']
        coll_name = entry['name']
        resolved = library.resolve(coll_id)
        if not resolved:
            continue
        folder, data = resolved
        archived = data.get('archived', False)

        docs = {}
        ir = None
        source_count = 0
        knowledge_units = 0

        if data.get('revisions') and data.get('active_revision') != 'pending':
            try:
                run = library.run(folder, data)
                corpus_path = run / 'corpus.json'
                if corpus_path.is_file():
                    corpus = read(corpus_path)
                    for s_entry in corpus.get('sources', []):
                        sp = safe_child(run, s_entry['path'])
                        if sp.is_file():
                            doc = read(sp)
                            docs[doc.get('source_id', s_entry.get('source_id', ''))] = doc
                    source_count = len(docs)
                ir_path = run / 'ir.json'
                if ir_path.is_file():
                    ir = read(ir_path)
                    knowledge_units = len(ir.get('units', []))
            except Exception:
                pass

        # Profile collection
        coll_clean = _clean_str(coll_name)
        coll_tokens = set(_tokenize(coll_name))

        # Check creators
        creators = set()
        for d in docs.values():
            c = d.get('creator')
            if c and str(c).strip():
                creators.add(str(c).strip())

        # Check source titles and filenames
        source_titles = [d.get('title') or d.get('filename') or '' for d in docs.values()]
        source_tokens = set()
        for st in source_titles:
            source_tokens.update(_tokenize(st))

        # Check knowledge units
        unit_tokens = set()
        if ir:
            for u in ir.get('units', []):
                unit_tokens.update(_tokenize(u.get('title', '')))

        # Score matching
        score = 0.0
        reasons = []

        # 1. Full collection name match
        if coll_clean and coll_clean in clean_incoming:
            score += 0.50
            reasons.append(f"Full collection name matched in content: '{coll_name}'")
        elif coll_tokens:
            # Token overlap with collection name
            name_overlap = coll_tokens & incoming_tokens
            if name_overlap:
                overlap_ratio = len(name_overlap) / len(coll_tokens)
                pts = min(0.40, 0.20 + 0.20 * overlap_ratio)
                score += pts
                sample_words = ', '.join(f"'{w}'" for w in sorted(name_overlap)[:3])
                reasons.append(f"Topic keywords match collection name ({sample_words})")

        # 2. Creator matching
        for creator in creators:
            creator_clean = _clean_str(creator)
            creator_tokens = set(_tokenize(creator))
            if creator_clean and (creator_clean in clean_incoming or (creator_tokens and creator_tokens.issubset(incoming_tokens))):
                score += 0.45
                reasons.append(f"Creator matches existing sources: '{creator}'")
                break
            elif creator_tokens & incoming_tokens:
                matched_creator_toks = creator_tokens & incoming_tokens
                score += 0.25
                sample = ', '.join(f"'{w}'" for w in sorted(matched_creator_toks)[:2])
                reasons.append(f"Source creator keyword match: {sample}")
                break

        # 3. Source titles overlap
        if source_tokens:
            shared_source_toks = (source_tokens & incoming_tokens) - coll_tokens
            if shared_source_toks:
                pts = min(0.25, 0.08 * len(shared_source_toks))
                score += pts
                sample = ', '.join(f"'{w}'" for w in sorted(shared_source_toks)[:3])
                reasons.append(f"Matches topics in existing sources ({sample})")

        # 4. Knowledge units overlap
        if unit_tokens:
            shared_unit_toks = (unit_tokens & incoming_tokens) - coll_tokens - source_tokens
            if shared_unit_toks:
                pts = min(0.15, 0.05 * len(shared_unit_toks))
                score += pts
                sample = ', '.join(f"'{w}'" for w in sorted(shared_unit_toks)[:3])
                reasons.append(f"Matches compiled knowledge concepts ({sample})")

        score = min(1.0, round(score, 2))
        is_candidate = score >= 0.25

        summary_item = {
            'name': coll_name,
            'collection_id': coll_id,
            'source_count': source_count,
            'knowledge_units': knowledge_units,
            'archived': archived,
            'is_candidate': is_candidate,
        }
        all_summary.append(summary_item)

        if is_candidate:
            confidence = 'high' if score >= 0.60 else 'medium' if score >= 0.35 else 'low'
            collection_scores.append({
                'name': coll_name,
                'collection_id': coll_id,
                'score': score,
                'confidence': confidence,
                'reasons': reasons,
                'source_count': source_count,
                'knowledge_units': knowledge_units,
                'archived': archived,
            })

    # Sort candidates by score descending
    collection_scores.sort(key=lambda c: c['score'], reverse=True)
    top_candidates = collection_scores[:4]

    if top_candidates:
        suggested_action = 'ask_with_candidates'
        guidance = (
            f"Found {len(top_candidates)} candidate collection(s) matching the incoming content. "
            "Ask the user which collection to add this source data to. Present the top candidate(s) "
            "with brief reasons, list the other existing collections, and offer the option to create a new collection."
        )
    else:
        suggested_action = 'ask_all_collections'
        guidance = (
            "No existing collection had a high topical match. Present the existing collections to the user "
            "and ask if they would like to add this to one of them or create a new collection for it."
        )

    return {
        'has_collections': True,
        'total_collections': len(all_summary),
        'candidates': top_candidates,
        'all_collections': all_summary,
        'suggested_action': suggested_action,
        'prompt_guidance': guidance,
    }
