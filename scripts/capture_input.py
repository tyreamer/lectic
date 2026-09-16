"""Expand cheap share inputs into canonical captures; no retrieval or inference."""
from urllib.parse import urlparse
import re

from ec import fingerprint, validate_schema


def expand_input(value):
    # Imported lazily to keep the adapter separate from capture storage.
    from capture_store import instant, validate_capture

    validate_schema(value, 'capture-input')
    captured_at = instant(value['captured_at']).isoformat()
    original = value['original_value']
    # Only a whole, valid HTTP(S) value is classified as URL-only. In prose,
    # retain the first supplied link as metadata and keep ALL original text.
    stripped = original.strip()
    links = re.findall(r'https?://[^\s<>"\x00-\x1f]+', original, re.IGNORECASE)
    url = ''
    for candidate in links:
        if candidate != stripped:
            candidate = candidate.rstrip('.,;:!?')
            while candidate.endswith(')') and candidate.count(')') > candidate.count('('):
                candidate = candidate[:-1]
        try:
            parsed = urlparse(candidate)
            if parsed.hostname:
                url = candidate
                break
        except ValueError:
            continue
    event = {
        'schema_version': '1.0',
        # A stable content identity survives reimport, sync paths, and fresh sessions.
        # The time distinguishes intentional saves of identical content.
        'capture_id': 'capture-' + fingerprint({'adapter': 'share-input-v1',
            'captured_at': captured_at, 'original_value': original})[:48],
        'captured_at': captured_at,
        'original_value': original,
        'source_type': 'url' if url and stripped == url else 'text',
        'capture_status': 'captured',
        'processing_status': 'pending',
        'provenance': {'adapter': 'share-input-v1', 'origin': 'supplied-value'},
        'url': url,
        'shared_text': original,
        'user_note': value.get('user_note', ''),
        'requested_collections': value.get('requested_collections', []),
    }
    return validate_capture(event)
