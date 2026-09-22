"""Portable method + selected evidence excerpts. Full originals stay in local collections."""
from pathlib import Path
import shutil
from ec import (ROOT, VERSION, require, fingerprint, read, write, text_write, inventory,
                validate_schema, validate_units, validate_sources, validate_capability_data, skill_text)


def rendered_skill(cap):
    return skill_text(cap).replace('[canonical sources](sources/corpus.json)', '[source excerpts](sources/excerpts.json)') + (
        '\nThis scoped export contains relevant quotations, not full original transcripts or user work. '
        'Its validator checks internal evidence linkage; original-byte verification requires the private collection. '
        'Citations do not establish permission to publish or independent correctness.\n')


def selected_excerpts(selected, docs, segments):
    relevant = {}
    for unit in selected:
        for e in unit['evidence']:
            sid = e['source_id']; doc = docs[sid]; seg = segments[(sid, e['segment_id'])]
            if sid not in relevant:
                relevant[sid] = {k:doc[k] for k in ('source_id','title','creator','filename','url','content_hash')}
                relevant[sid]['excerpts'] = []
            excerpt = {k:seg[k] for k in ('segment_id','start','end','speaker')}
            excerpt['quote'] = e['quote']
            if excerpt not in relevant[sid]['excerpts']: relevant[sid]['excerpts'].append(excerpt)
    return list(relevant.values())


def export_method(run, ir, cap, destination):
    corpus, docs, segments = validate_sources(run)
    require(ir['corpus_id'] == corpus['corpus_id'], 'Export knowledge belongs to another source revision')
    validate_units(ir['units'], docs, segments)
    validate_capability_data(ir, {'schema_version':VERSION, 'ir_hash':fingerprint(ir), 'capabilities':[cap]})
    destination = Path(destination).resolve()
    require(destination.name == cap['capability_id'] and not destination.exists(), 'Use a new export folder named after the method')
    require(not destination.is_relative_to(Path(run).resolve()), 'Export outside the source run')
    selected = [u for u in ir['units'] if u['unit_id'] in cap['unit_ids']]
    from store import staged
    with staged(destination, '.export-') as staging:
        text_write(staging / 'SKILL.md', rendered_skill(cap))
        write(staging / 'capability.json', cap)
        write(staging / 'references/knowledge.json', selected)
        write(staging / 'sources/excerpts.json', selected_excerpts(selected,docs,segments))
        write(staging / 'evidence/index.json', [{'unit_id':u['unit_id'], 'status':u['status'], 'evidence':u['evidence']} for u in selected])
        write(staging / 'examples/examples.json', cap['examples'])
        shutil.copytree(ROOT / 'schemas', staging / 'schemas')
        (staging / 'checks').mkdir()
        shutil.copy2(ROOT / 'scripts/ec.py', staging / 'checks/ec.py')
        shutil.copy2(Path(__file__), staging / 'checks/scoped_export.py')
        text_write(staging / 'checks/validate.py', 'import sys\nfrom pathlib import Path\nsys.dont_write_bytecode = True\nfrom ec import validate_package\nvalidate_package(Path(__file__).resolve().parent.parent)\nprint("Package valid")\n')
        manifest = {'schema_version':VERSION,'export_format':'scoped-1','capability_id':cap['capability_id'],
                    'corpus_id':ir['corpus_id'],'ir_hash':fingerprint(ir),'files':inventory(staging)}
        write(staging / 'manifest.json', manifest)
        from ec import validate_package
        validate_package(staging)
    return destination


def validate_scoped(folder, manifest):
    folder = Path(folder)
    allowed = {'SKILL.md','capability.json','references/knowledge.json','sources/excerpts.json',
               'evidence/index.json','examples/examples.json','checks/ec.py','checks/scoped_export.py','checks/validate.py'}
    required = allowed | {'schemas/manifest.schema.json','schemas/source-excerpts.schema.json','schemas/knowledge-unit.schema.json','schemas/capability.schema.json','schemas/capabilities.schema.json'}
    files = set(manifest['files'])
    require(required <= files and all(f in allowed or (f.startswith('schemas/') and f.endswith('.schema.json') and f.count('/') == 1) for f in files), 'Scoped package contains missing or unrequested private files')
    cap = read(folder / 'capability.json'); validate_schema(cap, 'capability')
    require(cap['capability_id'] == manifest['capability_id'], 'Capability identity mismatch')
    units = read(folder / 'references/knowledge.json')
    excerpts = read(folder / 'sources/excerpts.json'); validate_schema(excerpts, 'source-excerpts')
    docs, segments, triples = {}, {}, set()
    for doc in excerpts:
        sid = doc['source_id']; require(sid not in docs, 'Duplicate source excerpt ID'); docs[sid] = doc
        for e in doc['excerpts']:
            require((e['start'] is None and e['end'] is None) or
                    (e['start'] is not None and e['end'] is not None and 0 <= e['start'] <= e['end']), 'Malformed excerpt timestamps')
            require((sid,e['segment_id'],e['quote']) not in triples, 'Duplicate excerpt')
            key = (sid, e['segment_id'])
            segments.setdefault(key, {'text':'','speaker':e['speaker']})['text'] += '\n' + e['quote']
            triples.add((sid, e['segment_id'], e['quote']))
    validate_units(units, docs, segments)
    used = {(e['source_id'],e['segment_id'],e['quote']) for u in units for e in u['evidence']}
    require(used == triples, 'Excerpt set differs from selected evidence')
    require({u['unit_id'] for u in units} == set(cap['unit_ids']), 'Selected units mismatch')
    partial_ir = {'units':units}
    validate_capability_data(partial_ir, {'schema_version':VERSION,'ir_hash':fingerprint(partial_ir),'capabilities':[cap]})
    require(read(folder / 'examples/examples.json') == cap['examples'], 'Examples mismatch')
    require(read(folder / 'evidence/index.json') == [{'unit_id':u['unit_id'],'status':u['status'],'evidence':u['evidence']} for u in units], 'Evidence index mismatch')
    require((folder / 'SKILL.md').read_text(encoding='utf-8') == rendered_skill(cap), 'Skill differs from validated method')
    return manifest
