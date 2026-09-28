"""Two decisions a save must not leave to improvisation.

Where the item goes (one strong match files itself, several plausible ones earn a
single question, nothing plausible falls to Inbox), and what Lectic can honestly
read from it later (YouTube captions are retrievable; almost every other link is
kept as a reference only).
"""
from __future__ import annotations

from urllib.parse import urlsplit

STRONG_MATCH = 0.50   # a full collection-name match scores this on its own
CLEAR_MARGIN = 0.15   # how far the top candidate must lead the runner-up to file itself

PLATFORM_NAMES = {
    'instagram.com': 'Instagram', 'tiktok.com': 'TikTok', 'x.com': 'X', 'twitter.com': 'X',
    'facebook.com': 'Facebook', 'linkedin.com': 'LinkedIn', 'reddit.com': 'Reddit',
    'threads.net': 'Threads', 'substack.com': 'Substack', 'medium.com': 'Medium',
}


def _normalize_url(url):
    url = (url or '').strip()
    if url and '://' not in url and not url.startswith('//'):
        return 'https://' + url
    return url


def _platform(url):
    norm = _normalize_url(url)
    host = (urlsplit(norm).hostname or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    for domain, label in PLATFORM_NAMES.items():
        if host == domain or host.endswith('.' + domain):
            return label
    return host or 'that link'


def _retriever(url):
    """The adapter that could actually fetch this link's content, or None."""
    try:
        from linked_sources import resolver_for
        return resolver_for(_normalize_url(url))
    except Exception:
        return None


def describe_source(url='', text='', files=()):
    """What arrived and what Lectic will ever be able to read from it.

    `content_available` is the honest answer to "will the words in this thing be
    searchable and quotable?": false for a link nothing can retrieve.
    """
    url = (url or '').strip()
    if url:
        adapter = _retriever(url)
        if adapter is not None:
            if getattr(adapter, 'adapter', '') == 'youtube-captions':
                return {'source_type': 'youtube', 'platform': 'YouTube', 'retrieval': 'captions',
                        'content_available': True,
                        'what_lectic_gets': 'This is a YouTube link. Processing the collection retrieves the English '
                                            'captions, so what is said in the video becomes searchable and quotable.'}
            if getattr(adapter, 'adapter', '') == 'web-article':
                platform = _platform(url)
                return {'source_type': 'web', 'platform': platform, 'retrieval': 'article_text',
                        'content_available': True,
                        'what_lectic_gets': f'This is a web article from {platform}. Processing the collection retrieves '
                                            'and cleans the article text, so what is written becomes searchable and quotable.'}
        platform = _platform(url)
        return {'source_type': 'web', 'platform': platform, 'retrieval': 'reference_only',
                'content_available': False,
                'what_lectic_gets': f'{platform} links are saved as a reference only. Lectic keeps the link, the '
                                    'title and any note, and cannot read the post itself, so nothing inside it '
                                    'will be searchable or quotable. Paste the words you care about to save those.'}
    if (text or '').strip():
        return {'source_type': 'text', 'platform': '', 'retrieval': 'supplied_text', 'content_available': True,
                'what_lectic_gets': 'Pasted text is stored verbatim and is fully searchable and quotable.'}
    return {'source_type': 'file', 'platform': '', 'retrieval': 'attached_file', 'content_available': True,
            'what_lectic_gets': 'The file is stored as the original. Transcript and text files become searchable '
                                'when the collection is processed; other formats are kept but not read.'}


def _or_list(names):
    names = list(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} or {names[1]}'
    return ', '.join(names[:-1]) + f', or {names[-1]}'


def decide_placement(project, *, url='', text='', title='', files=(), note='', collections=()):
    """Resolve the destination before anything is written.

    decision is one of: explicit, auto_filed, needs_clarification, inbox_fallback.
    """
    requested = [str(c).strip() for c in (collections or ()) if str(c).strip()]
    if requested:
        return {'decision': 'explicit', 'collections': requested, 'candidates': [], 'all_collections': [],
                'question': '',
                'guidance': 'The user named the destination. Confirm the save and stop; do not ask a question.'}

    from candidate_collections import find_candidate_collections
    cand = find_candidate_collections(project, url=url, text=text, title=title, files=files, note=note)
    ranked = cand['candidates']
    everything = [c['name'] for c in cand['all_collections']]
    top = ranked[0] if ranked else None
    runner_up = ranked[1]['score'] if len(ranked) > 1 else 0.0

    if top and not top['archived'] and top['score'] >= STRONG_MATCH and (len(ranked) == 1 or top['score'] - runner_up >= CLEAR_MARGIN):
        return {'decision': 'auto_filed', 'collections': [top['name']], 'candidates': ranked,
                'all_collections': everything, 'question': '',
                'guidance': f"Filed in {top['name']} because it was the one clear match. Name that collection in "
                            'your confirmation so the user can correct it, and ask nothing.'}

    if ranked:
        question = f"Should this go in {_or_list(c['name'] for c in ranked)}, or somewhere new?"
        return {'decision': 'needs_clarification', 'collections': ['Inbox'], 'candidates': ranked,
                'all_collections': everything, 'question': question,
                'guidance': 'Several collections fit, so the item is already safe in Inbox. Ask exactly this one '
                            'short question and nothing more. When the user answers, move it with '
                            "lectic_capture(action='move', items=[capture_id], to=[name]), or save a new "
                            'collection by name if they want somewhere new.'}

    return {'decision': 'inbox_fallback', 'collections': ['Inbox'], 'candidates': [], 'all_collections': everything,
            'question': '',
            'guidance': 'Nothing already saved was a plausible fit, so this went to Inbox. Say that plainly in the '
                        'confirmation and ask no question.'}


def confirmation_line(placement, source):
    """The sentence the assistant should actually say after a save."""
    honesty = source['what_lectic_gets']
    decision = placement['decision']
    if decision == 'explicit':
        return f"Saved to {_or_list(placement['collections'])}. {honesty}"
    if decision == 'auto_filed':
        return (f"Saved to {placement['collections'][0]}, which was the closest fit. {honesty} "
                'Tell me if it belongs somewhere else.')
    if decision == 'needs_clarification':
        return f"Saved. {honesty} {placement['question']}"
    return f'Saved to your Inbox: nothing already in your library was a close fit. {honesty}'
