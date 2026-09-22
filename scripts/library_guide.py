"""Read saved work and persist grounded, personal next-use suggestions outside IR."""
from pathlib import Path
import json

from ec import (ROOT, fingerprint, read, require, safe_child, text_write,
                validate_ir, validate_package, validate_schema, validate_sources, write)
from collection_store import Library
from home import session_path as legacy_session_path, resolve_run, storage_mode


def library_view(project='.', collection=None):
    """Read-only: never activate, prepare, rebuild or migrate a collection."""
    from capability_maps import load_map
    from goal_workflow import validate_build
    library = Library(project)
    rows, references, issues = [], {}, []
    entries = library.index['collections']
    if collection:
        resolved = library.resolve(collection)
        require(resolved is not None, 'Collection is not saved in this project')
        entries = [e for e in entries if e['collection_id'] == resolved[1]['collection_id']]
    for entry in entries:
        row = {'name': entry['name'], 'collection_id': entry['collection_id'], 'issues': [],
               'methods': [], 'opportunities': [], 'sources': [], 'captures': []}
        rows.append(row)
        try:
            folder, data = library.resolve(entry['collection_id'])
            row['archived'] = data.get('archived', False)
            run = library.run(folder, data)
            _, docs, _ = validate_sources(run)
            ir = validate_ir(run) if (run / 'ir.json').exists() else None
            row.update(source_revision=data['active_revision'], ir_hash=fingerprint(ir) if ir else None,
                       knowledge_status='processed' if ir and ir['units'] else 'sources_saved')
            row['sources'] = [{'title': d['title'] or d['filename'], 'url': d['url']} for d in docs.values()]
            if (folder / 'pack-origin.json').is_file():
                origin = read(folder / 'pack-origin.json')
                row['pack'] = {'pack_id': origin['manifest']['pack_id'], 'verification': origin['install']['verification'],
                               'installed_at': origin['install']['installed_at'], 'readable': origin['install']['readable'],
                               'methods': [{'title': m['title'], 'description': m['description'],
                                            'method': str(folder / 'pack' / 'methods' / m['build_id'] / 'method.md')} for m in origin['manifest']['methods']]}
        except (OSError, ValueError, KeyError) as exc:
            row['issues'].append(str(exc))
            continue
        seen, built_opportunities = set(), {}
        for build_id in reversed(data['builds']):
            try:
                build = safe_child(folder / 'builds', build_id)
                verification = validate_build(build)
                manifest = read(build / 'manifest.json')
                cap = read(build / 'method.json')['capability']
                current = manifest['source_revision'] == data['active_revision'] and manifest['ir_hash'] == row['ir_hash']
                status = 'ready' if current and cap['capability_id'] not in seen else 'saved_version'
                seen.add(cap['capability_id'])
                ref = 'method:' + build_id
                method = build / 'method.md' if manifest.get('result_format') == 'outcome-1' else build / 'method' / cap['capability_id'] / 'SKILL.md'
                item = {'reference': ref, 'kind': 'method', 'status': status, 'title': cap['title'],
                        'collection': data['name'], 'input': cap['inputs'], 'output': cap['output_contract'],
                        'description': cap['description'], 'boundaries': cap['boundaries'],
                        'conflicts': cap['conflict_policy'], 'unit_ids': cap['unit_ids'], 'examples': cap['examples'],
                        'method': str(method), 'result': str(build / 'result.md'), 'build': str(build),
                        'validation': verification, 'binding': manifest['method_hash']}
                row['methods'].append(item)
                references[ref] = item
                if status == 'ready':
                    try:
                        origin, _ = json.JSONDecoder().raw_decode(read(build / 'brief.json')['context'].lstrip())
                        if type(origin) is dict and type(origin.get('opportunity')) is dict:
                            built_opportunities[(origin.get('capability_map'), origin['opportunity'].get('opportunity_id'))] = ref
                    except (ValueError, KeyError):
                        pass  # Ordinary goal context is not a map selection.
            except (OSError, ValueError, KeyError) as exc:
                row['issues'].append(f'Saved build {build_id}: {exc}')
        index_path = folder / 'maps/index.json'
        if index_path.exists():
            try:
                index = read(index_path)
                require(type(index) is dict and type(index.get('maps')) is list, 'Malformed map index')
                map_ids = index['maps']
                if map_ids:
                    # Reading must not change the last map shown or numbered selection.
                    record = load_map(folder, data, map_ids[-1])
                    current = record['binding']['source_revision'] == data['active_revision'] and record['binding']['ir_hash'] == row['ir_hash']
                    for op in record['draft']['opportunities']:
                        if op['opportunity_id'] not in record['recommended_ids']:
                            continue
                        ref = 'opportunity:' + record['map_id'] + ':' + op['opportunity_id']
                        item = {'reference': ref, 'kind': 'opportunity', 'status': 'can_build' if current else 'needs_refresh',
                                'title': op['title'], 'collection': data['name'], 'input': op['input'], 'output': op['output'],
                                'description': op['transformation'], 'boundaries': op['boundaries'],
                                'conflicts': [c['handling'] for c in op['conflicts']], 'unit_ids': op['unit_ids'],
                                'map_id': record['map_id'], 'opportunity_id': op['opportunity_id'],
                                'support': op['support'], 'support_reason': op['support_reason']}
                        built_ref = built_opportunities.get((record['map_id'], op['opportunity_id']))
                        if current and built_ref:
                            item.update(status='already_built', method_reference=built_ref)
                        row['opportunities'].append(item)
                        references[ref] = item
                    row['map_reason'] = record['draft']['no_opportunities_reason']
            except (OSError, ValueError, KeyError) as exc:
                row['issues'].append('Capability Map: ' + str(exc))
        if (library.root / 'capture/state').exists():
            try:
                from capture_store import CaptureStore
                row['captures'] = CaptureStore(project).listing(data['collection_id'])['items']
            except (OSError, ValueError, KeyError) as exc:
                row['issues'].append('Capture availability: ' + str(exc))
    # Older runs predate named collections. Surface actual packages without
    # adopting or rewriting them, so returning users don't get an empty library.
    legacy, legacy_runs = [], []
    if not collection:
        runs = {p.parent for p in (library.root / 'runs').glob('*/corpus.json')}
        session_path = legacy_session_path(library.root, library.project)
        if session_path.exists():
            try:
                session = read(session_path)
                if session.get('active_run'):
                    runs.add(resolve_run(library.root, library.project, session['active_run']))
            except (OSError, ValueError, KeyError, AttributeError) as exc:
                issues.append('Earlier session: ' + str(exc))
        for run in sorted(runs):
            try:
                require(run.is_relative_to(library.root) or run.is_relative_to(library.project), 'Earlier run lives outside this home and project')
                _, docs, _ = validate_sources(run)
                ir = validate_ir(run) if (run / 'ir.json').exists() else None
                legacy_runs.append({'location': str(run), 'source_count': len(docs),
                    'sources': [d['title'] or d['filename'] for d in docs.values()],
                    'status': 'knowledge_saved' if ir and ir['units'] else 'sources_saved',
                    'ir_hash': fingerprint(ir) if ir else None,
                    'next_step': 'Reuse this saved run directly, or adopt it into a named collection when further discovery is requested. No source re-upload is needed.'})
            except (OSError, ValueError, KeyError) as exc:
                issues.append('Earlier run ' + run.name + ': ' + str(exc))
        for path in sorted((library.root / 'capabilities').glob('*/*/manifest.json')):
            try:
                package = path.parent
                safe_child(library.root, package.relative_to(library.root).as_posix())
                manifest = validate_package(package)
                cap = read(package / 'capability.json')
                ref = 'legacy:' + fingerprint(package.relative_to(library.root).as_posix())[:24]
                item = {'reference': ref, 'kind': 'legacy', 'status': 'saved_version', 'title': cap['title'],
                        'collection': 'Earlier compilation', 'input': cap['inputs'], 'output': cap['output_contract'],
                        'description': cap['description'], 'boundaries': cap['boundaries'],
                        'conflicts': cap['conflict_policy'], 'unit_ids': cap['unit_ids'], 'examples': cap['examples'],
                        'method': str(package / 'SKILL.md'), 'binding': fingerprint(manifest)}
                legacy.append(item)
                references[ref] = item
            except (OSError, ValueError, KeyError) as exc:
                issues.append(f'Earlier package {path.parent.name}: {exc}')
    view = {'phase': 'lectic_library', 'scope': str(library.project), 'home': str(library.root),
            'storage_mode': storage_mode(library.root, library.project), 'collection_filter': collection,
            'collections': rows, 'legacy_methods': legacy, 'legacy_runs': legacy_runs, 'references': references, 'issues': issues,
            'context_policy': 'Use only relevant context actually available in this conversation, saved user context, or explicitly supplied host memory. Do not infer a user profile from saved sources.'}
    view['binding_hash'] = fingerprint(view)
    view['markdown'] = render_library(view)
    return view


def render_library(view):
    lines = ['# Your Lectic library', '', 'Saved in this project. Other projects and platform memories are not searched.', '']
    if not view['collections'] and not view['legacy_methods'] and not view['legacy_runs']:
        lines += ['No saved collections or methods found here. If you used another project, open that project; no re-upload is needed when the originals are still saved there.', '']
    for row in view['collections']:
        lines += ['## ' + row['name'] + (' (archived)' if row.get('archived') else ''),
                  f"Saved: {len(row['sources'])} source document(s); {len(row['captures'])} capture(s).", '']
        for item in row['methods']:
            label = 'Ready to use' if item['status'] == 'ready' else 'Saved earlier version; review changes before reuse'
            lines += [f"- **{item['title']} — {label}.** Give it: {item['input']} Get: {item['output']}",
                      f"  [Method](<{item['method']}>) · [Previous result](<{item['result']}>)"]
        for item in row['opportunities']:
            if item['status'] == 'already_built': continue
            label = 'Can build next' if item['status'] == 'can_build' else 'Suggestion needs refreshing'
            lines += [f"- **{item['title']} — {label}.** Give it: {item['input']} Get: {item['output']}"]
        if not row['methods'] and not row['opportunities'] and not row['issues']:
            lines += ['No reusable method is registered yet. ' + ('Discover what this saved knowledge can become.' if row.get('knowledge_status') == 'processed' else 'Process the supplied content when you want to discover uses.')]
        for capture in row['captures']:
            if capture['processing_status'] != 'processed':
                lines += [f"- {capture['title']}: {capture['processing_status'].replace('_', ' ')}. {capture['retrieval']}"]
        lines += ['- Needs attention: ' + issue for issue in row['issues']]
        lines += ['']
    for run in view['legacy_runs']:
        lines += [f"- **Earlier saved material — {run['status'].replace('_', ' ')}:** " + '; '.join(run['sources']),
                  f"  [Saved run](<{run['location']}>) — {run['next_step']}"]
    for item in view['legacy_methods']:
        lines += [f"- **{item['title']} — saved from an earlier compilation.** Give it: {item['input']} Get: {item['output']}", f"  [Open saved skill](<{item['method']}>)"]
    lines += ['- Needs attention: ' + issue for issue in view['issues']]
    lines += ['', 'Saved and structurally checked does not mean independently tested for effectiveness.', '']
    return '\n'.join(lines)


def validate_guide(draft, view):
    validate_schema(draft, 'use-guide')
    require(draft['binding_hash'] == view['binding_hash'], 'Use guide is stale; refresh the library before recommending uses')
    contexts = {c['context_id'] for c in draft['context']}
    require(len(contexts) == len(draft['context']), 'Duplicate personal context ID')
    ids = [c['card_id'] for c in draft['cards']]
    require(len(ids) == len(set(ids)), 'Duplicate use card ID')
    for card in draft['cards']:
        require(card['reference'] in view['references'], 'Use card refers to an unsaved method or opportunity')
        ref = view['references'][card['reference']]
        require(ref['status'] in {'ready', 'can_build', 'saved_version'}, 'Refresh stale opportunities before suggesting a build')
        require(card['availability'] == ('build_first' if ref['kind'] == 'opportunity' else 'ready' if ref['status'] == 'ready' else 'saved_version'), 'A proposed or historical capability cannot be labeled ready')
        require(set(card['unit_ids']) <= set(ref['unit_ids']), 'Use example cites knowledge outside its saved basis')
        require(set(card['context_ids']) <= contexts, 'Personalized suggestion has no recorded context basis')
    require(draft['recommended_card'] in ids if ids else draft['recommended_card'] == '', 'Recommend a shown use card or explain why none are supported')
    require(ids or draft['no_suggestions_reason'].strip(), 'Explain the gap instead of inventing uses')
    return draft


def render_guide(record):
    draft = record['draft']
    lines = ['# What you can do with your saved material', '', draft['saved_summary'], '']
    for n, card in enumerate(draft['cards'], 1):
        status = {'ready': 'Ready to use', 'build_first': 'Can build next', 'saved_version': 'Uses a saved earlier version'}[card['availability']]
        lines += [f"## {n}. {card['title']} — {status}", card['why_useful'], '',
                  '**You provide:** ' + card['input'], '**You get:** ' + card['output'],
                  '**Try saying:** ' + card['try_prompt'], '**Limits:** ' + '; '.join(card['limits']), '']
    if draft['cards']:
        chosen = next(c for c in draft['cards'] if c['card_id'] == draft['recommended_card'])
        lines += ['**Suggested first use:** ' + chosen['title'] + '. ' + draft['recommendation_reason'], '']
    else:
        lines += [draft['no_suggestions_reason'], '']
    if draft['question']:
        lines += [draft['question'], '']
    lines += ['Suggestions are source-linked and assistant-reviewed; usefulness and personal fit still need a real task.', '']
    return '\n'.join(lines)


def use_guide(*, project='.', collection=None, action='prepare', draft=None, guide_id=None, select=None):
    from capability_maps import capability_map
    view = library_view(project, collection)
    root = Library(project).root / 'use-guides'
    index_path = root / 'index.json'
    index = read(index_path) if index_path.exists() else {'guides': [], 'last_shown': None}
    require(type(index) is dict and type(index.get('guides')) is list and
            all(type(uid) is str for uid in index['guides']) and len(index['guides']) == len(set(index['guides'])) and
            (index.get('last_shown') is None or index['last_shown'] in index['guides']), 'Malformed use-guide index')
    if action == 'prepare':
        return {'phase': 'prepare_use_guide', 'library': view, 'agent_task': {
            'prompt': str(ROOT / 'prompts/guide-use.md'), 'schema': str(ROOT / 'schemas/use-guide.schema.json'),
            'draft': str(root / 'drafts' / (view['binding_hash'] + '.json')), 'binding_hash': view['binding_hash']}}
    if action == 'save':
        require(draft is not None, 'Write the use-guide draft before saving')
        value = read((Path(project) / draft).resolve())
        validate_guide(value, view)
        record = {'schema_version': '1.0', 'collection_filter': collection, 'library': view, 'draft': value}
        uid = 'guide-' + fingerprint(record)[:24]
        record['guide_id'] = uid
        path = root / (uid + '.json')
        if path.exists(): require(read(path) == record, 'Immutable use guide differs')
        else: write(path, record)
        text_write(root / (uid + '.md'), render_guide(record))
        if uid not in index['guides']: index['guides'].append(uid)
    else:
        uid = guide_id or index['last_shown']
        require(uid in index['guides'], 'No shown use guide; prepare one from the saved library')
        record = read(safe_child(root, uid + '.json'))
        require(record['guide_id'] == uid == 'guide-' + fingerprint({k: v for k, v in record.items() if k != 'guide_id'})[:24], 'Use guide hash mismatch')
        validate_guide(record['draft'], record['library'])
        # Resolve the original display scope, never reinterpret its numbers against another view.
        require(collection is None or collection == record['collection_filter'], 'Use guide belongs to another library view')
        view = library_view(project, record['collection_filter'])
    stale = record['draft']['binding_hash'] != view['binding_hash']
    if action == 'select':
        require(not stale, 'Use guide is stale; show refreshed suggestions before selecting')
        selector = str(select or '').strip().lstrip('#')
        cards = record['draft']['cards']
        if selector.isdigit():
            number = int(selector)
            require(1 <= number <= len(cards), 'Select a shown use card')
            card = cards[number - 1]
        else:
            hits = [c for c in cards if selector.casefold() in {c['card_id'].casefold(), c['title'].casefold()}]
            require(len(hits) == 1, 'Select a shown use by its title or number')
            card = hits[0]
        ref = view['references'][card['reference']]
        if ref['kind'] == 'opportunity':
            result = capability_map(project=project, collection=ref['collection'], action='select',
                                    map_id=ref['map_id'], select=ref['opportunity_id'],
                                    use_context={'guide_id': uid, 'card': card,
                                        'context': [c for c in record['draft']['context'] if c['context_id'] in card['context_ids']]})
            return {**result, 'selected_use': card, 'guidance': str(ROOT / 'prompts/guide-use.md')}
        return {'phase': 'use_saved_method', 'selected_use': card, 'saved_method': ref,
                'guidance': str(ROOT / 'prompts/guide-use.md'),
                'instruction': 'Use actual work already supplied; otherwise ask only for the input on this card. Preserve the saved method and create a new result. Historical versions need an explicit version choice before representing them as current.'}
    require(action in {'save', 'show'}, 'Unknown use-guide action')
    index['last_shown'] = uid
    write(index_path, index)
    return {'phase': 'use_guide', 'guide_id': uid, 'path': str(root / (uid + '.md')),
            'stale': stale, 'guide': record['draft'], 'markdown': render_guide(record)}
