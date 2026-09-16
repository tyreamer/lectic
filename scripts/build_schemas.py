"""Regenerate checked-in Draft 2020-12 schemas; no runtime dependencies."""
from pathlib import Path
from ec import TYPES, VERSION, write

S = {'type': 'string', 'minLength': 1}
NULL_S = {'type': ['string', 'null'], 'minLength': 1}
ID = {'type': 'string', 'pattern': '^[a-z0-9]+(?:-[a-z0-9]+)*$', 'maxLength': 64}
HASH = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
SID = {'type': 'string', 'pattern': '^src-[a-f0-9]{24}$'}
CID = {'type': 'string', 'pattern': '^corpus-[a-f0-9]{64}$'}
EMPTY = {'type': 'string'}
V = {'const': VERSION, 'type': 'string'}


def obj(**props):
    return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}


def arr(item, minimum=0, maximum=None):
    result = {'type': 'array', 'items': item, 'minItems': minimum, 'uniqueItems': True}
    if maximum is not None: result['maxItems'] = maximum
    return result


evidence = obj(source_id=SID, segment_id={'type': 'string', 'pattern': '^seg-[0-9]{6}$'}, quote=S)
unit = obj(schema_version=V, unit_id=ID, type={'enum': TYPES}, status={'enum': ['explicit', 'inferred', 'synthesized']},
           title=S, statement=S, scope=S, derivation=EMPTY, evidence=arr(evidence, 1),
           attribution=arr(obj(source_id=SID, name=S)),
           relations=arr(obj(kind={'enum': ['supports', 'contradicts', 'requires', 'duplicates', 'refines']}, target=ID)))
capability = obj(schema_version=V, capability_id=ID, title=S, description={**S, 'maxLength': 1024},
                 rationale=S, inputs=S, output_contract=S, unit_ids=arr(ID, 1),
                 steps=arr(obj(instruction=S, unit_ids=arr(ID, 1)), 1), boundaries=arr(S, 1),
                 conflict_policy=EMPTY, checks=arr(S, 1),
                 examples=arr(obj(input=S, output=S, unit_ids=arr(ID, 1), status={'const': 'synthetic'}), 1))
schemas = {
    'source': obj(schema_version=V, source_id=SID, filename=S, title=NULL_S, creator=NULL_S,
                  url={'type': ['string', 'null'], 'pattern': '^https?://[^\\s/?#]+(?:[/?#][^\\s]*)?$'},
                  caption_type={'enum': ['unknown', 'manual', 'automatic', 'synthetic']}, content_hash=HASH,
                  raw_path=S, segments=arr(obj(segment_id={'type': 'string', 'pattern': '^seg-[0-9]{6}$'},
                      start={'type': ['number', 'null'], 'minimum': 0}, end={'type': ['number', 'null'], 'minimum': 0},
                      speaker=NULL_S, text=S, raw_text=S), 1)),
    'corpus': obj(schema_version=V, corpus_id=CID, sources=arr(obj(source_id=SID, path=S, document_hash=HASH), 1)),
    'knowledge-unit': unit,
    'extraction': obj(schema_version=V, corpus_id=CID, source_id=SID, note=EMPTY, units=arr(unit)),
    'ir': obj(schema_version=V, corpus_id=CID, units=arr(unit, 1),
              coverage=arr(obj(source_id=SID, unit_ids=arr(ID), note=EMPTY), 1)),
    'capability': capability,
    'capabilities': obj(schema_version=V, ir_hash=HASH, capabilities=arr(capability, 1, 3)),
    'discovery-assessment': obj(schema_version=V, ir_hash=HASH, no_capability_reason=EMPTY,
                                weakly_supported=arr(obj(topic=S, reason=S, unit_ids=arr(ID)), maximum=3)),
    'manifest': obj(schema_version=V, capability_id=ID, corpus_id=CID, ir_hash=HASH, files={'type': 'object'}),
}
schemas['session'] = obj(schema_version=V, active_run=S,
                         last_built=obj(run=S, capability_id=ID),
                         pending_request=obj(run=S, intent={'enum':['compile','discover','build','use','compare']},
                                             select={'type':['string','null']}, build_all={'type':'boolean'}))
schemas['session']['required'] = ['schema_version', 'active_run']
schemas['manifest']['properties']['export_format'] = {'const':'scoped-1'}
schemas['source-excerpts'] = arr(obj(source_id=SID, title=NULL_S, creator=NULL_S, filename=S, url=NULL_S, content_hash=HASH,
                                    excerpts=arr(obj(segment_id=S, start={'type':['number','null'],'minimum':0},
                                                     end={'type':['number','null'],'minimum':0}, speaker=NULL_S, quote=S),1)),1)
schemas['brief'] = obj(schema_version=V, objective=S, context=EMPTY, constraints=arr(S),
                       work=obj(label=S, text=EMPTY), desired_result=S, success_criteria=arr(S,1))
schemas['collection'] = obj(schema_version=V, collection_id=ID, name=S, active_revision=ID,
                            revisions=arr(obj(revision_id=ID, corpus_id=CID, run=S),1), briefs=arr(ID), builds=arr(ID))
schemas['coverage-assessment'] = obj(schema_version=V, brief_id=ID, ir_hash=HASH,
                                     decision={'enum':['reuse','extend']}, source_ids=arr(SID), reason=S,
                                     unsupported=arr(S))
schemas['goal-method'] = obj(schema_version=V, brief_id=ID, ir_hash=HASH, capability=capability)
finding = obj(title=S, priority={'enum':['high','medium','low']}, assessment=S, proposed_change=S, unit_ids=arr(ID,1))
step = obj(action=S, done_when=S, unit_ids=arr(ID,1))
schemas['work-result'] = obj(schema_version=V, brief_id=ID, ir_hash=HASH, method_hash=HASH,
                             target={'enum':['review','checklist']}, assessment=S, findings=arr(finding),
                             proposed_revision=EMPTY, checklist=arr(step), disagreements=arr(S), limitations=arr(S),
                             unsupported=arr(S), additional_general_advice=arr(S))
schemas['goal-build'] = obj(schema_version=V, build_id=ID, collection_id=ID, source_revision=ID,
                            corpus_id=CID, ir_hash=HASH, knowledge_path=S, brief_id=ID, brief_hash=HASH,
                            method_hash=HASH, result_hash=HASH, target={'enum':['review','checklist']},
                            compiler_hash=HASH, files={'type':'object'})

# Additive contracts keep all existing 1.0 briefs and builds readable.
INTENTS = ['create','review','improve','decide','plan','do','learn','reference']
schemas['corpus']['properties']['sources']['minItems'] = 0
schemas['brief']['properties']['intent'] = {'enum':INTENTS}
schemas['brief']['properties']['intent_reason'] = S
schemas['collection']['properties']['archived'] = {'type':'boolean'}
schemas['collection']['properties']['revision_history'] = {'type':'array','items':ID,'minItems':1}
schemas['goal-build']['properties']['target'] = {'enum':INTENTS+['checklist']}
schemas['goal-build']['properties']['result_format'] = {'const':'outcome-1'}
schemas['outcome'] = obj(schema_version={'const':'1.1'}, brief_id=ID, ir_hash=HASH, method_hash=HASH,
    target={'enum':INTENTS}, summary=S,
    sections=arr(obj(kind={'enum':['deliverable','assessment','revision','options','recommendation','steps','lesson','exercise','feedback','answer']},
                     title=S, content=S, unit_ids=arr(ID), status={'enum':['explicit','inferred','synthesized','original','user_context']})),
    disagreements=arr(S), limitations=arr(S), unsupported=arr(S), additional_general_advice=arr(S))

# Discovery is derived from IR; it does not add recommendation fields to knowledge units.
CATEGORIES = ['create','review','improve','decide','plan','do','learn','reference','automate','evaluate']
factor = obj(level={'enum':['high','medium','low']}, reason=S)
opportunity = obj(opportunity_id=ID, title=S, problem=S, input=S, transformation=S, output=S,
    categories=arr({'enum':CATEGORIES},1), support={'enum':['strong','supported','weak']},
    support_reason=S, unit_ids=arr(ID,1),
    grounding=obj(rules=arr(ID), procedures=arr(ID), criteria=arr(ID), examples=arr(ID), conditions=arr(ID)),
    boundaries=arr(S,1), conflicts=arr(obj(unit_ids=arr(ID,2), handling=S)),
    reuse=factor, actionability=factor, judgment=factor, saved_work=factor,
    beyond_qa=obj(verdict={'enum':['distinct','modest','none']}, reason=S),
    targets=arr(obj(label=S, delivery={'enum':['text','skill','future']}, description=S),1),
    ranking_reason=S)
schemas['capability-map-draft'] = obj(schema_version={'const':'1.0'}, binding_hash=HASH,
    category_assessments=arr(obj(category={'enum':CATEGORIES}, reason=S, unit_ids=arr(ID)),10,10),
    opportunities=arr(opportunity,0,8), no_opportunities_reason=EMPTY,
    semantic_review=obj(status={'const':'assistant-reviewed'}, limitations=S))
schemas['capability-map'] = obj(schema_version={'const':'1.0'}, map_id=ID,
    binding=obj(collection_id=ID, source_revision=ID, ir_hash=HASH, compiler_version=S,
                compiler_hash=HASH, discovery_version=S),
    draft=schemas['capability-map-draft'], recommended_ids=arr(ID,0,5),
    source_coverage={'type':'object'}, unit_hashes={'type':'object'})

# Cheap capture envelopes and personal annotations are independent of source/IR schemas.
attachment = obj(path=S, filename=S)
attachment['properties'].update(sha256=HASH, byte_size={'type':'integer','minimum':0})
schemas['capture'] = obj(schema_version={'const':'1.0'}, capture_id=ID, captured_at=S,
    original_value=S, source_type={'enum':['url','text','image','video','file','unknown']},
    capture_status={'const':'captured'}, processing_status={'const':'pending'},
    provenance=obj(adapter=S, origin=EMPTY), shared_text=EMPTY, url=EMPTY, title=EMPTY,
    user_note=EMPTY, requested_collections=arr(S), attachments=arr(attachment))
schemas['capture']['required'] = ['schema_version','capture_id','captured_at','original_value','source_type',
                                  'capture_status','processing_status','provenance']
schemas['capture-annotation'] = obj(schema_version={'const':'1.0'}, annotation_id=ID, capture_id=ID,
    annotated_at=S, user_note=EMPTY, add_collections=arr(S))
schemas['capture-state'] = obj(schema_version={'const':'1.0'}, capture_id=ID, envelope_hash=HASH,
    imported_at=S, collection_ids=arr(ID), source_ids=arr(SID), attachment_blobs=arr(obj(path=S, blob_hash=HASH)),
    annotation_ids=arr(ID), capture_status={'const':'captured'},
    processing_status={'enum':['pending','awaiting_retrieval','partially_processed','processed','needs_attention']},
    issues=arr(S))
schemas['capture-state']['properties']['retrieval'] = obj(
    adapter=S, adapter_version=S, status={'enum':['unavailable','retrieved']},
    original_url=S, canonical_url=NULL_S, attempted_at=S, retrieved_at=NULL_S,
    source_ids=arr(SID), error=NULL_S)
schemas['linked-retrieval'] = obj(schema_version={'const':'1.0'}, adapter=S, adapter_version=S,
    canonical_url=S, retrieved_at=S, records=arr(obj(filename=S, blob_hash=HASH,
        metadata=obj(title=NULL_S, creator=NULL_S, url=S, caption_type={'enum':['manual','automatic']})),1))

if __name__ == '__main__':
    for name, schema in schemas.items():
        write(Path(__file__).resolve().parent.parent / 'schemas' / f'{name}.schema.json',
              {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': name, **schema})
    print(f'Wrote {len(schemas)} schemas')
