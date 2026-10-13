"""Decode iPhone Share Sheet requests without fetching linked content."""
import json
import re

from ec import require


def decode_share(raw, content_type='text/plain'):
    text = raw.decode('utf-8')
    if content_type.split(';')[0].strip().lower() == 'application/json':
        payload = json.loads(text)
        require(isinstance(payload, dict), 'Capture body must be a JSON object')
    else:
        payload = {'value': text}
    value = payload.get('value') or payload.get('url') or payload.get('text') or ''
    require(isinstance(value, str) and value.strip(), 'Nothing to save: share a link or text')
    value = value.strip()
    collections = payload.get('collections')
    if collections is None:
        collection = payload.get('collection')
        collections = [collection] if collection else []
    require(isinstance(collections, list) and all(isinstance(c, str) and c.strip() for c in collections),
            'collections must be a list of collection names')
    note, title = payload.get('note') or '', payload.get('title') or ''
    require(isinstance(note, str) and isinstance(title, str), 'note and title must be text')
    is_url = re.fullmatch(r'https?://\S+', value, re.IGNORECASE) is not None
    # Instagram may share a URL alone or a URL plus text. Keep mixed input
    # intact instead of treating all of it as one malformed URL.
    return {'url': value if is_url else '', 'text': '' if is_url else value,
            'note': note, 'title': title, 'collections': collections}
