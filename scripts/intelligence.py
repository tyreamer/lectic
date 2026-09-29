"""Automatic knowledge relationships and selective, portable task context.

This is deliberately a derived layer.  Collections and their evidence remain the
source of truth; users do not have to label, move, or connect them.  Rebuilding the
view after a source or knowledge revision is therefore safe and deterministic.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from collection_store import Library
from ec import fingerprint, read, validate_ir, validate_schema, validate_sources


STOP = {
    'a','an','and','are','as','at','be','for','from','how','i','in','is','it','me','my','of','on','or',
    'our','the','this','to','use','using','we','with','you','your','knowledge','planning','guide','tips'
}
TRAVEL = {'travel','trip','vacation','holiday','flight','flights','hotel','hotels','itinerary','train','rail','airport'}
CODING = {'code','coding','software','developer','programming','react','python','api','architecture'}
EUROPE = {'europe','european','italy','italian','france','french','spain','spanish','germany','german','switzerland',
          'swiss','portugal','greece','austria','belgium','netherlands','rome','paris','london','barcelona','venice'}
JAPAN = {'japan','japanese','tokyo','kyoto','osaka','hokkaido'}
TASK_MARKERS = {'today','tomorrow','tonight','next','deadline','budget','days','day','week','fix','specific','currently'}
PERSONAL_MARKERS = {'prefer','prefers','preference','preferences','dislike','dislikes','like','likes','always','never',
                    'my','mine','favorite','favourite'}


def tokens(value):
    words = set(re.findall(r"[a-z0-9]+", (value or '').casefold())) - STOP
    if words & (EUROPE | JAPAN | {'asia','africa','america','hawaii'}): words.add('travel')
    if words & {'react','python','api','javascript','typescript'}: words.add('coding')
    if words & {'train','rail','flight','airport','hotel','itinerary'}: words.add('travel')
    return words


def _profile(library, entry):
    folder, data = library.resolve(entry['collection_id'])
    run = library.run(folder, data)
    _, docs, _ = validate_sources(run)
    ir = validate_ir(run) if (run / 'ir.json').is_file() else None
    units = ir['units'] if ir else []
    text = ' '.join([data['name']] + [d.get('title') or d['filename'] for d in docs.values()] +
                    [f"{u['title']} {u['statement']} {u['scope']}" for u in units])
    words = tokens(text)
    personal_hits = sum(bool(tokens(u['title'] + ' ' + u['statement']) & PERSONAL_MARKERS) for u in units)
    name_personal = bool(re.match(r'^(my|personal|our)\b', data['name'], re.I)) or 'preferences' in data['name'].casefold()
    layer = 'personal' if name_personal or (units and personal_hits >= max(1, len(units) // 2)) else 'domain'
    return {'collection_id': data['collection_id'], 'name': data['name'], 'layer': layer,
            'topics': sorted(words), 'source_count': len(docs), 'knowledge_units': len(units),
            'active_revision': data['active_revision'], 'ir_hash': fingerprint(ir) if ir else None,
            'units': units, 'sources': docs, 'archived': data.get('archived', False)}


def _relationship(source, target, kind, reason, shared, evidence=()):
    return {'from': source['collection_id'], 'to': target['collection_id'], 'kind': kind,
            'reason': reason, 'shared_topics': sorted(shared), 'evidence': list(evidence)}


def knowledge_graph(project='.'):
    """Build a plain-data relationship view without changing the library."""
    library = Library(project)
    profiles = [_profile(library, e) for e in library.index['collections']]
    active = [p for p in profiles if not p['archived']]
    relationships = []
    for left in active:
        for right in active:
            if left['collection_id'] == right['collection_id']: continue
            lt, rt = set(left['topics']), set(right['topics'])
            shared = lt & rt
            meaningful = shared - {'travel','coding'}
            evidence = [{'collection_id': left['collection_id'], 'knowledge_revision': left['ir_hash']},
                        {'collection_id': right['collection_id'], 'knowledge_revision': right['ir_hash']}]
            if left['layer'] == 'personal' and right['layer'] == 'domain' and shared:
                relationships.append(_relationship(left, right, 'personal_preference_relevant_to',
                    f"{left['name']} contains preferences that can help with {right['name']} tasks.", shared, evidence))
            elif left['layer'] == right['layer'] == 'domain' and set(tokens(right['name'])) < set(tokens(left['name'])):
                relationships.append(_relationship(left, right, 'specializes',
                    f"{left['name']} is a more specific area of {right['name']}.", shared, evidence))
            elif left['collection_id'] < right['collection_id'] and (meaningful or len(shared) >= 2):
                relationships.append(_relationship(left, right, 'related_to',
                    f"{left['name']} and {right['name']} cover some of the same subject.", shared, evidence))
    public_profiles = [{k:v for k,v in p.items() if k not in {'units','sources','topics'}} |
                       {'topics': p['topics'][:24]} for p in profiles]
    graph = {'schema_version':'1.0', 'generated_at':datetime.now(timezone.utc).isoformat(),
             'collections':public_profiles, 'relationships':relationships}
    graph['graph_id'] = 'graph-' + fingerprint({k:v for k,v in graph.items() if k != 'generated_at'})[:24]
    validate_schema(graph, 'knowledge-graph')
    return graph


def _query_features(intent):
    raw = tokens(intent)
    expanded = set(raw)
    if raw & TRAVEL or raw & EUROPE or raw & JAPAN: expanded.add('travel')
    if raw & CODING: expanded.add('coding')
    if raw & EUROPE: expanded |= {'europe','european'}
    if raw & JAPAN: expanded |= {'japan','japanese'}
    return raw, expanded


def _unit_score(unit, query):
    title = tokens(unit['title']); body = tokens(unit['statement'] + ' ' + unit['scope'])
    return 5 * len(title & query) + 2 * len(body & query) + (1 if title & {'preference','preferences'} else 0)


def compose_context(project='.', intent='', task_context='', max_units=24):
    """Select useful units for an intent, following only helpful relationships."""
    if not str(intent).strip(): raise ValueError('Describe the task Lectic should prepare for')
    library = Library(project)
    profiles = [_profile(library, e) for e in library.index['collections']]
    raw, query = _query_features(intent + ' ' + (task_context or ''))
    ranked = []
    for p in profiles:
        if p['archived'] or not p['units']: continue
        pt = set(p['topics']); topical = query & pt
        score = 4 * len(tokens(p['name']) & query) + 2 * len(topical)
        if p['layer'] == 'personal':
            # Personal knowledge follows the user only when its domain is relevant.
            personal_domain = (pt & query) | ({'travel'} if 'travel' in pt & query else set()) | ({'coding'} if 'coding' in pt & query else set())
            if not personal_domain: continue
            score += 4
        if score <= 0: continue
        ranked.append((score, p))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['name'].casefold()))

    chosen, seen = [], {}
    for collection_score, p in ranked:
        units = sorted(p['units'], key=lambda u: (-_unit_score(u, query), u['unit_id']))
        focused = [u for u in units if _unit_score(u, query) > 0] or units[:2]
        take = min(6, max_units - len(chosen))
        for unit in focused[:take]:
            if len(chosen) >= max_units: break
            key = re.sub(r'[^a-z0-9]+', ' ', unit['statement'].casefold()).strip()
            if key in seen:
                seen[key]['also_supported_by'].append(p['name']); continue
            citations = [{'source_id': e['source_id'], 'segment_id': e['segment_id'], 'quote': e['quote'],
                          'source': (p['sources'].get(e['source_id'], {}).get('title') or
                                     p['sources'].get(e['source_id'], {}).get('filename'))}
                         for e in unit['evidence']]
            item = {'collection':p['name'], 'collection_id':p['collection_id'], 'layer':p['layer'],
                    'unit_id':unit['unit_id'], 'title':unit['title'], 'statement':unit['statement'],
                    'scope':unit['scope'], 'status':unit['status'], 'evidence':citations, 'also_supported_by':[]}
            chosen.append(item); seen[key] = item

    activated = []
    for _, p in ranked:
        count = sum(u['collection_id'] == p['collection_id'] or p['name'] in u['also_supported_by'] for u in chosen)
        if count:
            activated.append({'name':p['name'], 'collection_id':p['collection_id'], 'layer':p['layer'],
                              'selected_units':count,
                              'why':('Your preferences are relevant to this task.' if p['layer']=='personal' else
                                     f"It covers {', '.join(sorted(query & set(p['topics']))[:4]) or 'the task subject'}." )})

    gaps = []
    if raw & JAPAN and not any(set(p['topics']) & JAPAN for _,p in ranked):
        gaps.append({'topic':'Japan', 'message':"I know how you like to travel and can use the travel knowledge you have now. I don't have much Japan-specific knowledge yet. Guides, videos, or notes could make future Japan trips more specific."})
    elif raw & EUROPE and not any(set(p['topics']) & EUROPE for _,p in ranked):
        gaps.append({'topic':'Europe', 'message':"I can use your broader travel knowledge now, but I don't have much Europe-specific knowledge yet. Guides, videos, or notes could make future European trips more specific."})
    if not chosen:
        gaps.append({'topic':'task', 'message':"I don't have saved knowledge that clearly matches this yet. The task can still continue using the details you provided."})

    task = {'label':"This task's details", 'layer':'task', 'text':task_context or intent,
            'persistent':False, 'reason':'Useful now; not automatically saved as reusable knowledge.'}
    result = {'schema_version':'1.0', 'intent':intent, 'using':activated, 'task_context':task,
              'knowledge':chosen, 'gaps':gaps,
              'summary':_context_summary(activated, gaps),
              'portable_context':_portable_context(intent, activated, task, chosen, gaps)}
    result['context_id'] = 'context-' + fingerprint(result)[:24]
    validate_schema(result, 'working-context')
    return result


def _context_summary(using, gaps):
    if not using: return "Lectic did not find saved knowledge that clearly matches this task."
    names = ', '.join(x['name'] for x in using)
    text = f"Using {names} for this task."
    if gaps: text += ' ' + gaps[0]['message']
    return text


def _portable_context(intent, using, task, units, gaps):
    lines = ['# WayKit context', '', 'Task: ' + intent, '', '## Using for this task', '']
    lines += [f"- {x['name']} — {x['why']}" for x in using]
    lines += [f"- {task['label']} — {task['reason']}", '', '## Relevant knowledge', '']
    for unit in units:
        lines += [f"### {unit['title']} ({unit['collection']})", unit['statement'], 'Scope: ' + unit['scope']]
        for e in unit['evidence']:
            lines.append(f"- Evidence: {e['source'] or e['source_id']} [{e['segment_id']}] — “{e['quote']}”")
        lines.append('')
    if gaps: lines += ['## Helpful gaps', ''] + ['- ' + g['message'] for g in gaps] + ['']
    return '\n'.join(lines)


def explain_collection(project='.', selector=None):
    library = Library(project)
    resolved = library.resolve(selector)
    if not resolved: raise ValueError('Name a saved knowledge area to explain')
    profile = _profile(library, {'collection_id':resolved[1]['collection_id']})
    graph = knowledge_graph(project)
    rels = [r for r in graph['relationships'] if profile['collection_id'] in {r['from'],r['to']}]
    source_list = [{'title':d.get('title') or d['filename'], 'url':d.get('url'), 'source_id':sid}
                   for sid,d in profile['sources'].items()]
    return {'name':profile['name'], 'layer':profile['layer'], 'knows':[u['title'] for u in profile['units']],
            'knowledge_units':len(profile['units']), 'sources':source_list, 'relationships':rels,
            'summary':f"{profile['name']} has {len(profile['units'])} reusable ideas from {len(source_list)} source(s). " +
                      ('It contains preferences that can follow you into relevant tasks.' if profile['layer']=='personal' else
                       'It contains reusable subject knowledge.')}


def assess_import(project='.', *, url='', text='', title='', files=(), note=''):
    """Recommend enrichment versus a distinct related area without asking users to model a graph."""
    from candidate_collections import find_candidate_collections
    matches = find_candidate_collections(project, url=url, text=text, title=title, files=files, note=note)
    incoming = tokens(' '.join([url, text[:5000], title, note] + [str(f) for f in files]))
    layer = 'personal' if incoming & PERSONAL_MARKERS else ('task' if incoming & TASK_MARKERS and len(incoming) < 20 else 'domain')
    top = matches['candidates'][0] if matches['candidates'] else None
    material = ' '.join([url, text, title, note])
    source_volume = max(1, len(files) + len(re.findall(r'https?://', material)))
    hours = sum(int(n) for n in re.findall(r'\b(\d{1,3})\s*hours?\b', material, re.I))
    substantial = source_volume >= 8 or hours >= 10
    specialized = bool(top and incoming - tokens(top['name']) - STOP and top['score'] < .60 and substantial)
    if layer == 'task':
        decision, message = 'keep_with_task', "This looks specific to the current task, so I would use it now without turning it into permanent knowledge."
    elif top and not specialized:
        decision, message = 'enrich_existing', f"This substantially overlaps {top['name']}, so I would add what is new there instead of creating another small knowledge area."
    elif top:
        decision, message = 'create_related', f"This is related to {top['name']} but specialized enough to stay useful on its own, so I would keep it separate and connect the two."
    else:
        decision, message = 'create_new', "This is reusable knowledge that is not already covered, so I would create one new knowledge area for it."
    return {'layer':layer, 'decision':decision, 'message':message, 'related_to':top, 'candidates':matches['candidates']}
