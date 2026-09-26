"""Versioned opportunity discovery over immutable expertise snapshots.

The assistant authors semantic judgments. These guards validate references and
minimum evidence shapes, not entailment or real-world effectiveness.
"""
import json
from pathlib import Path
from store import home_transaction
from ec import (ROOT, VERSION, fingerprint, read, require, safe_child, text_write,
                validate_ir, validate_schema, write)
from collection_store import Library

DISCOVERY_VERSION = 'opportunities-1'
CATEGORIES = ('create','review','improve','decide','plan','do','learn','reference','automate','evaluate')
ROLE_TYPES = {
    'rules': {'principle','heuristic','procedure','framework'},
    'procedures': {'procedure'},
    'criteria': {'principle','heuristic','framework','warning','failure_pattern'},
    'examples': {'example'},
    # Applicability may be recorded in the scope of any unit.
    'conditions': None,
}


def rank(opportunity):
    """Lexicographic qualitative priorities, never a confidence score."""
    levels = {'high':0,'medium':1,'low':2}
    return ({'strong':0,'supported':1,'weak':2}[opportunity['support']],
            levels[opportunity['reuse']['level']], levels[opportunity['actionability']['level']],
            levels[opportunity['saved_work']['level']], levels[opportunity['judgment']['level']],
            {'distinct':0,'modest':1,'none':2}[opportunity['beyond_qa']['verdict']],
            opportunity['opportunity_id'])


def contradictions(ir, chosen):
    return {tuple(sorted((u['unit_id'], r['target']))) for u in ir['units'] for r in u['relations']
            if r['kind']=='contradicts' and (u['unit_id'] in chosen or r['target'] in chosen)}


def validate_draft(draft, ir, binding):
    validate_schema(draft,'capability-map-draft')
    require(draft['binding_hash']==fingerprint(binding), 'Discovery draft is stale for its source/IR/compiler binding')
    units={u['unit_id']:u for u in ir['units']}
    assessments=draft['category_assessments']
    require({a['category'] for a in assessments}==set(CATEGORIES), 'Assess each opportunity category exactly once')
    for a in assessments:
        require(set(a['unit_ids'])<=units.keys(), 'Category assessment cites unknown knowledge')
    ids=[o['opportunity_id'] for o in draft['opportunities']]
    titles=[o['title'].casefold() for o in draft['opportunities']]
    require(len(ids)==len(set(ids)) and len(titles)==len(set(titles)), 'Duplicate opportunity identity/title')
    require(draft['opportunities'] or draft['no_opportunities_reason'].strip(), 'Explain why no opportunities are supported')
    for o in draft['opportunities']:
        chosen=set(o['unit_ids']); g=o['grounding']
        require(chosen<=units.keys(), 'Opportunity cites unknown knowledge')
        for role, refs in g.items():
            require(set(refs)<=chosen, 'Grounding must cite selected expertise')
            allowed=ROLE_TYPES[role]
            require(allowed is None or all(units[uid]['type'] in allowed for uid in refs), 'Evidence type does not support '+role)
        for conflict in o['conflicts']:
            require(set(conflict['unit_ids'])<=units.keys(), 'Conflict cites unknown knowledge')
        covered={tuple(sorted(c['unit_ids'])) for c in o['conflicts']}
        require(contradictions(ir,chosen)<=covered, 'Opportunity omits an applicable source disagreement')
        if o['support']=='weak':
            continue  # Explicit gaps are saved but cannot be selected as builds.
        cats=set(o['categories'])
        if cats & {'create','improve','decide','plan','automate'}:
            require(g['rules'], 'Actionable opportunity needs source rules, not just facts')
        if 'do' in cats:
            require(g['procedures'], 'DO needs a source procedure')
        if cats & {'review','evaluate'}:
            require(g['criteria'], 'Review/evaluation needs source criteria')
        if o['support']=='strong' and cats-{'reference','learn'}:
            require(g['examples'] and g['conditions'], 'Strong actionable support needs examples and conditions')
        if cats-{'reference','learn'}:
            require(o['beyond_qa']['verdict']!='none', 'Actionable opportunities must explain value beyond Q&A')
        require(any(t['delivery']!='future' for t in o['targets']), 'A recommended opportunity needs a currently deliverable form')
        for t in o['targets']:
            if t['delivery']=='skill':
                require(g['rules'] or g['procedures'] or g['criteria'], 'Reusable skill needs an actionable source method')
    return draft


def render_map(record):
    opportunities={o['opportunity_id']:o for o in record['draft']['opportunities']}
    lines=['# Capability Map','',f"Map: `{record['map_id']}`",'',
           'Ranked by source support, repeat usefulness, actionability, saved work, judgment and value beyond Q&A.', '']
    for i, uid in enumerate(record['recommended_ids'],1):
        o=opportunities[uid]
        lines += [f"## {i}. {o['title']}",o['problem'],'',
                  '**Give it:** '+o['input'], '**It does:** '+o['transformation'], '**Get back:** '+o['output'],
                  '**Support:** '+o['support']+' — '+o['support_reason'],
                  f"**Source coverage:** {len(record['source_coverage'][uid])} source(s); {len(o['unit_ids'])} knowledge unit(s).",
                  '**Best for:** '+', '.join(c.upper() for c in o['categories']),
                  '**Reuse:** '+o['reuse']['reason'], '**Beyond ordinary Q&A:** '+o['beyond_qa']['verdict']+' — '+o['beyond_qa']['reason'],
                  '**Why ranked here:** '+o['ranking_reason'],
                  '**Can become:** '+ '; '.join(t['label']+' ('+t['delivery']+': '+t['description']+')' for t in o['targets']),
                  '**Limits:** '+'; '.join(o['boundaries']),
                  '**Disagreements:** '+('; '.join(c['handling'] for c in o['conflicts']) or 'None recorded for selected evidence.'),
                  '**Evidence units:** '+', '.join(o['unit_ids']), '']
    if not record['recommended_ids']:
        lines += [record['draft']['no_opportunities_reason'] or 'Only weak opportunities were found; more material is needed.', '']
    weak=[o for o in opportunities.values() if o['support']=='weak']
    if weak:
        lines += ['## Gaps, not build recommendations']+[f"- {o['title']}: {o['support_reason']}" for o in weak]
    lines += ['', 'Source linkage and evidence-shape checks passed. Semantic assessments are assistant-reviewed, not independently verified; effectiveness is untested.', '']
    return '\n'.join(lines)


def load_map(folder, data, map_id):
    record=read(safe_child(folder/'maps',map_id+'.json'))
    validate_schema(record,'capability-map')
    require(record['map_id']==map_id=='map-'+fingerprint({k:v for k,v in record.items() if k!='map_id'})[:24], 'Map hash/identity mismatch')
    binding=record['binding']
    require(binding['collection_id']==data['collection_id'], 'Map belongs to another collection')
    revision=next((r for r in data['revisions'] if r['revision_id']==binding['source_revision']),None)
    require(revision is not None, 'Map source revision is missing')
    run=safe_child(folder,revision['run'])
    ir=validate_ir(run,run/'history'/f"{binding['ir_hash']}.json")
    require(fingerprint(ir)==binding['ir_hash'], 'Map IR hash mismatch')
    validate_draft(record['draft'],ir,binding)
    expected=make_record(binding,record['draft'],ir)
    require(record==expected, 'Map ranking, coverage or evidence hashes differ')
    return record


def make_record(binding,draft,ir):
    validate_draft(draft,ir,binding)
    units={u['unit_id']:u for u in ir['units']}
    ranked=sorted((o for o in draft['opportunities'] if o['support']!='weak'),key=rank)[:5]
    record={'schema_version':'1.0','binding':binding,'draft':draft,
            'recommended_ids':[o['opportunity_id'] for o in ranked],
            'source_coverage':{o['opportunity_id']:sorted({e['source_id'] for uid in o['unit_ids'] for e in units[uid]['evidence']}) for o in draft['opportunities']},
            'unit_hashes':{uid:fingerprint(u) for uid,u in units.items()}}
    record['map_id']='map-'+fingerprint(record)[:24]
    validate_schema(record,'capability-map')
    return record


def compare_maps(old,new):
    a={o['opportunity_id']:o for o in old['draft']['opportunities']}
    b={o['opportunity_id']:o for o in new['draft']['opportunities']}
    changes={'new':sorted(b.keys()-a.keys()),'removed_or_invalidated':sorted(a.keys()-b.keys()),
             'strengthened':[],'weakened':[],'newly_supported':[],'affected_by_contradictions':[],
             'changed_evidence':[],'changed_description':[],'unchanged':[]}
    support={'weak':0,'supported':1,'strong':2}
    for uid in sorted(a.keys() & b.keys()):
        x,y=a[uid],b[uid]
        if support[y['support']]>support[x['support']]: changes['strengthened'].append(uid)
        if support[y['support']]<support[x['support']]: changes['weakened'].append(uid)
        if x['support']=='weak' and y['support']!='weak': changes['newly_supported'].append(uid)
        if x['conflicts']!=y['conflicts']: changes['affected_by_contradictions'].append(uid)
        refs=set(x['unit_ids'])|set(y['unit_ids'])
        if x['unit_ids']!=y['unit_ids'] or any(old['unit_hashes'].get(u)!=new['unit_hashes'].get(u) for u in refs):
            changes['changed_evidence'].append(uid)
        if x!=y: changes['changed_description'].append(uid)
        elif uid not in changes['changed_evidence']: changes['unchanged'].append(uid)
    changes['assessment_note']='Strength changes compare assistant support judgments, not measured effectiveness. Added evidence alone does not prove stronger support.'
    return changes


@home_transaction
def capability_map(*,project='.',collection=None,action='discover',draft=None,map_id=None,
                   before=None,select=None,regenerate=False,reconciled=False,use_context=None):
    from goal_workflow import compiler_hash, work
    library=Library(project); resolved=library.resolve(collection)
    require(resolved is not None, 'Save a collection before discovering opportunities')
    folder,data=resolved
    index_path=folder/'maps/index.json'
    index=read(index_path) if index_path.exists() else {'maps':[],'last_shown':None}
    require(type(index) is dict and set(index)=={'maps','last_shown'} and type(index['maps']) is list
            and all(type(uid) is str for uid in index['maps']), 'Malformed map index')
    require(len(index['maps'])==len(set(index['maps'])) and
            (index['last_shown'] is None or index['last_shown'] in index['maps']), 'Malformed map history or last shown map')
    for uid in index['maps']: load_map(folder,data,uid)
    if action=='list': return {'phase':'capability_maps','maps':index['maps'],'last_shown':index['last_shown']}
    if action in {'inspect','compare','select'}:
        chosen_id=map_id or index['last_shown']
        require(chosen_id is not None, 'Discover a Capability Map first')
        record=load_map(folder,data,chosen_id)
        if action=='compare':
            require(chosen_id in index['maps'], 'Map must be registered before comparing its history')
            previous=before or next((uid for uid in reversed(index['maps'][:index['maps'].index(chosen_id)]) if uid!=chosen_id),None)
            require(previous is not None, 'Comparison needs two saved maps')
            return {'phase':'map_comparison','before':previous,'after':chosen_id,'changes':compare_maps(load_map(folder,data,previous),record)}
        if action=='select':
            run=library.run(folder,data)
            require(record['binding']['source_revision']==data['active_revision'] and
                    (run/'ir.json').exists() and fingerprint(validate_ir(run))==record['binding']['ir_hash'],
                    'Map is stale for active expertise; regenerate and show the new map before selecting')
            require(select is not None, 'Select a shown opportunity by number, title or ID')
            selector=str(select).strip().lstrip('#')
            if selector.isdigit():
                number=int(selector)
                require(1<=number<=len(record['recommended_ids']), 'Opportunity number is outside the shown map')
                selector=record['recommended_ids'][number-1]
            hits=[o for o in record['draft']['opportunities'] if selector.casefold() in {o['title'].casefold(),o['opportunity_id']}]
            require(len(hits)==1 and hits[0]['support']!='weak', 'Select a supported opportunity; weak entries explain gaps')
            opportunity=hits[0]
            # Build the reusable capability first, without requiring an instance of future user work.
            brief={'schema_version':VERSION,'intent':'create','intent_reason':'Build the selected reusable capability; its future uses are recorded in the opportunity.',
                   'objective':'Build '+opportunity['title']+': '+opportunity['transformation'],
                   'context':json.dumps({'capability_map':chosen_id,'opportunity':opportunity},ensure_ascii=False),
                   'constraints':opportunity['boundaries']+[c['handling'] for c in opportunity['conflicts']],
                   'work':{'label':'Capability specification, not an application input','text':''},
                   'desired_result':'Ready-to-use '+opportunity['title']+' method with input instructions, output contract and a worked synthetic example.',
                   'success_criteria':['Preserve the selected evidence, conditions and disagreements.',
                                       'Produce a usable method; do not just repeat the opportunity pitch.',
                                       'Explain supported delivery forms without claiming future integrations exist.']}
            path=folder/'map-selections'/f"{chosen_id}-{opportunity['opportunity_id']}.json"
            if use_context is not None:
                # Keep the selected application through interruption/building, in
                # private intent context rather than changing source knowledge.
                brief['context'] += '\n\nSelected next use (personal intent, not source evidence):\n' + json.dumps(use_context,ensure_ascii=False)
                path=path.with_name(path.stem+'-'+fingerprint(use_context)[:16]+'.json')
            if path.exists(): require(read(path)==brief,'Saved selection differs')
            else: write(path,brief)
            result=work(project=project,collection=data['collection_id'],brief=str(path))
            return {**result,'selected_map':chosen_id,'selected_opportunity':opportunity['opportunity_id']}
        if chosen_id not in index['maps']: index['maps'].append(chosen_id)
        index['last_shown']=chosen_id; write(index_path,index)
        active_run=library.run(folder,data)
        return {'phase':'capability_map','map':record,'markdown':render_map(record),'guidance':str(ROOT/'prompts/guide-use.md'),
                'stale_source_revision':record['binding']['source_revision']!=data['active_revision'],
                'stale_knowledge_revision':not (active_run/'ir.json').exists() or fingerprint(validate_ir(active_run))!=record['binding']['ir_hash']}
    require(action=='discover','Unknown Capability Map action')
    prepared=work(project=project,collection=data['collection_id'],action='prepare',reconciled=reconciled)
    if prepared['phase']!='knowledge_saved': return prepared
    folder,data=library.resolve(data['collection_id']); run=library.run(folder,data); ir=validate_ir(run)
    binding={'collection_id':data['collection_id'],'source_revision':data['active_revision'],'ir_hash':fingerprint(ir),
             'compiler_version':VERSION,'compiler_hash':compiler_hash(),'discovery_version':DISCOVERY_VERSION}
    if not regenerate and not draft:
        for uid in reversed(index['maps']):
            record=load_map(folder,data,uid)
            if record['binding']==binding:
                index['last_shown']=uid;write(index_path,index)
                return {'phase':'capability_map','map':record,'markdown':render_map(record),'guidance':str(ROOT/'prompts/guide-use.md')}
    draft_path=folder/'maps/drafts'/f'{fingerprint(binding)}.json'
    if draft:
        draft_path=(Path(project)/draft).resolve()
    if not draft_path.exists() or regenerate and not draft:
        return {'phase':'discover_opportunities','collection':data['name'],
                'agent_task':{'prompt':str(ROOT/'prompts/opportunity-discovery.md'),'ir':str(run/'ir.json'),
                              'binding':binding,'binding_hash':fingerprint(binding),'draft':str(draft_path),
                              'previous_map':index['maps'][-1] if index['maps'] else None,
                              'schema':str(ROOT/'schemas/capability-map-draft.schema.json')}}
    record=make_record(binding,read(draft_path),ir); uid=record['map_id']
    destination=folder/'maps'/f'{uid}.json'
    if destination.exists(): require(read(destination)==record,'Immutable map differs')
    else: write(destination,record)
    text_write(folder/'maps'/f'{uid}.md',render_map(record))
    if uid not in index['maps']: index['maps'].append(uid)
    index['last_shown']=uid;write(index_path,index)
    return {'phase':'capability_map','map':record,'path':str(destination),'markdown':render_map(record),'guidance':str(ROOT/'prompts/guide-use.md')}
