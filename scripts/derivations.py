"""Optional media provenance alongside, never inside, the stable source/IR contracts."""
from ec import validate_schema, require


def validate_derivations(record, documents):
    validate_schema(record, 'derivations')
    names = {d['filename'] for d in documents.values()}
    for item in record['records']:
        require(item['filename'] in names, 'Derivation names an unknown source document')
        if item['kind'] in {'transcript', 'ocr', 'visual_interpretation'}:
            doc = next(d for d in documents.values() if d['filename'] == item['filename'])
            require(doc['caption_type'] == 'automatic', 'Automatically derived text must remain automatic for older readers')
    return record
