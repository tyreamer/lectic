"""Linked-source routing and immutable acquisition cache, independent of knowledge/IR."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ec import digest, fingerprint, read, require, safe_child, validate_schema, write
from ingestors import TranscriptInput


def resolver_for(url):
    from ingestors.youtube import YouTubeIngestor
    for adapter in (YouTubeIngestor,):
        if adapter.accepts(url):
            return adapter(url)
    return None


@dataclass(frozen=True)
class RetrievedSource:
    receipt: dict
    records: list[TranscriptInput]


def retrieve(adapter, root, save_blob):
    """Reuse caption bytes after interrupted normalization. Caller owns the capture lock."""
    identity = {'adapter': adapter.adapter, 'adapter_version': adapter.version,
                'canonical_url': adapter.canonical_url}
    path = root / 'retrievals' / (fingerprint(identity) + '.json')
    if not path.exists():
        records = adapter.collect()
        require(records, 'Retriever returned no transcripts')
        receipt = {'schema_version': '1.0', **identity,
                   'retrieved_at': datetime.now(timezone.utc).isoformat(), 'records': []}
        for record in records:
            require(Path(record.filename).name == record.filename and Path(record.filename).suffix in {'.vtt', '.srt', '.txt', '.md'},
                    'Retriever returned an unsafe transcript filename')
            receipt['records'].append({'filename': record.filename, 'blob_hash': save_blob(record.raw), 'metadata': record.metadata})
        validate_schema(receipt, 'linked-retrieval')
        write(path, receipt)
    receipt = read(path)
    validate_schema(receipt, 'linked-retrieval')
    require(all(receipt[k] == v for k, v in identity.items()), 'Retrieval cache identity mismatch')
    try:
        captured = datetime.fromisoformat(receipt['retrieved_at'].replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid retrieval timestamp') from exc
    require(captured.tzinfo is not None, 'Retrieval timestamp must include a timezone')
    records = []
    for item in receipt['records']:
        raw = safe_child(root / 'blobs', item['blob_hash']).read_bytes()
        require(digest(raw) == item['blob_hash'], 'Retrieved caption bytes were modified')
        require(Path(item['filename']).name == item['filename'], 'Unsafe cached transcript filename')
        records.append(TranscriptInput(item['filename'], raw, item['metadata']))
    return RetrievedSource(receipt, records)
