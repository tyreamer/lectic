"""Agent-facing deterministic coordinator. Reasoning tasks are returned, not simulated."""
from pathlib import Path
from store import home_transaction
import re

from ec import (ROOT, VERSION, Invalid, assemble, digest, fingerprint, ingest_records, package, read,
                require, safe_child, validate_capabilities, validate_ir, validate_package,
                validate_schema, validate_sources, validate_units, write)
from home import relative_run, resolve_run, session_path as legacy_session_path, storage_root


def checkpoint_state(run, corpus, docs, segments):
    parts, errors, seen, units = [], [], set(), []
    for path in sorted((run / 'units').glob('*.json')):
        try:
            part = read(path)
            validate_schema(part, 'extraction')
            sid = part['source_id']
            require(part['corpus_id'] == corpus['corpus_id'], 'stale checkpoint')
            require(sid in docs and sid not in seen, 'duplicate or unknown checkpoint source')
            require(part['units'] or part['note'].strip(), 'omitted source needs a reason')
            require(all(any(e['source_id'] == sid for e in u['evidence']) for u in part['units']), 'unit does not cite its checkpoint source')
            if part['units']: validate_units(part['units'], docs, segments, check_relations=False)
            seen.add(sid); parts.append(part); units.extend(part['units'])
        except (Invalid, ValueError, OSError) as exc:
            errors.append({'path': str(path), 'reason': str(exc)})
    pending = [{'source_id': sid, 'source': str(run / f'sources/{sid}.json'),
                'checkpoint': str(run / f'units/{sid}.json')} for sid in sorted(set(docs)-seen)]
    return parts, units, pending, errors


def summary(docs, ir=None, caps=None):
    # Sum the union of caption intervals, not overlapping cues or inferred video length.
    seconds, timed = 0.0, 0
    for doc in docs.values():
        intervals = sorted((s['start'], s['end']) for s in doc['segments'] if s['start'] is not None and s['end'] is not None)
        if not intervals: continue
        timed += 1
        start, end = intervals[0]
        for a, b in intervals[1:]:
            if a <= end: end = max(end, b)
            else: seconds += end-start; start, end = a, b
        seconds += end-start
    result = {'transcripts': len(docs), 'caption_coverage_seconds': round(seconds, 3) if timed else None,
              'sources_with_timed_captions': timed, 'recording_duration_known': False}
    if ir is not None:
        units = {u['unit_id']: u for u in ir['units']}
        pairs = {tuple(sorted((u['unit_id'], r['target']))) for u in units.values() for r in u['relations'] if r['kind'] == 'contradicts'}
        result.update(knowledge_units=len(units), procedures=sum(u['type'] == 'procedure' for u in units.values()), disagreements=len(pairs))
        if caps:
            result['capabilities'] = [{'number': i, 'id': c['capability_id'], 'title': c['title'],
                                      'description': c['description'], 'benefit': c['rationale'],
                                      'supporting_sources': len({e['source_id'] for uid in c['unit_ids'] for e in units[uid]['evidence']}),
                                      'limitations': c['boundaries'], 'disagreements': c['conflict_policy']}
                                     for i, c in enumerate(caps['capabilities'], 1)]
    return result


def compile_workflow(input=None, output=None, *, project='.', metadata=None, intent=None,
                     select=None, build_all=False, reconciled=False, tasks=None, rubric=None):
    # Do not create a user home just to explain missing input or unavailable
    # retrieval. The mutable coordinator runs under one shared-home lock.
    home = storage_root(project)
    if input is None and not output and not legacy_session_path(home, project).exists():
        return {'phase': 'needs_input', 'message': 'Give me transcript files or point me at their folder.'}
    records = None
    if input is not None:
        from ingestors import adapter_for
        from ingestors.youtube import YouTubeIngestor
        location = str(input) if YouTubeIngestor.accepts(input) else str((Path(project) / input).resolve())
        records = adapter_for(location).collect(str((Path(project) / metadata).resolve()) if metadata else None)
    return _compile_workflow(input, output, project=project, metadata=metadata, intent=intent,
                             select=select, build_all=build_all, reconciled=reconciled,
                             tasks=tasks, rubric=rubric, records=records)


@home_transaction
def _compile_workflow(input=None, output=None, *, project='.', metadata=None, intent=None,
                      select=None, build_all=False, reconciled=False, tasks=None, rubric=None, records=None):
    project = Path(project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    home = storage_root(project)
    session_path = legacy_session_path(home, project)
    session = read(session_path) if session_path.exists() else {}
    require(type(session) is dict, 'Malformed saved compilation session')
    if session:
        # Accept the initial pre-versioned local session shape without losing its pointer.
        session.setdefault('schema_version', VERSION)
        validate_schema(session, 'session')
    metadata = str((project / metadata).resolve()) if metadata else None
    if input is not None:
        from ingestors import adapter_for
        from ingestors.youtube import YouTubeIngestor
        location = str(input) if YouTubeIngestor.accepts(input) else str((project / input).resolve())
        adapter = adapter_for(location)
        require(records is not None, 'Input preflight did not supply source records')
        snapshot = fingerprint([{'filename': r.filename, 'hash': digest(r.raw), 'metadata': r.metadata} for r in records])
        name = re.sub('[^a-z0-9]+', '-', Path(location).name.lower()).strip('-')[:32] or 'transcripts'
        run = (project / output).resolve() if output else home / 'runs' / f'{name}-{snapshot[:16]}'
        relative_run(home, project, run)
        if hasattr(adapter, 'folder'):
            require(not run.is_relative_to(adapter.folder), 'Output must be outside input folder')
        ingest_records(records, run)
    elif output:
        run = (project / output).resolve()
        relative_run(home, project, run)
    elif session.get('active_run'):
        run = resolve_run(home, project, session['active_run'])
    else:
        return {'phase': 'needs_input', 'message': 'Give me transcript files or point me at their folder.'}
    corpus, docs, segments = validate_sources(run)
    session['active_run'] = relative_run(home, project, run)
    def recorded_is_active(recorded):
        # Sessions written by project-local installs recorded a different relative form of the same run.
        try: return bool(recorded) and resolve_run(home, project, recorded) == run
        except Invalid: return False
    if intent is None and not select and not build_all and input is None and output is None:
        pending_request = session.get('pending_request', {})
        if recorded_is_active(pending_request.get('run')):
            intent, select, build_all = pending_request['intent'], pending_request['select'], pending_request['build_all']
    intent = intent or ('build' if select or build_all else 'compile')
    select = str(select) if select is not None else None
    require(not (build_all and select), 'Choose a capability or build all, not both')
    require(not build_all or intent not in {'use', 'compare'}, 'Use/compare needs one capability')
    session['schema_version'] = VERSION
    session['pending_request'] = {'run': session['active_run'], 'intent': intent, 'select': select, 'build_all': build_all}
    validate_schema(session, 'session')
    write(session_path, session)

    def response(phase, **kwargs):
        return {'phase': phase, 'run': str(run), 'summary': summary(docs), **kwargs}

    parts, units, pending, errors = checkpoint_state(run, corpus, docs, segments)
    if pending or errors:
        return response('extract', agent_task={'prompt': str(ROOT / 'prompts/extract.md'),
                                              'pending_sources': pending, 'repairs': errors})
    if not units:
        return response('no_supported_knowledge', message='I reviewed the transcripts but did not find enough supported methods to build a useful capability.',
                        omissions=[p['note'] for p in parts])
    try:
        validate_units(units, docs, segments)
    except Invalid as exc:
        return response('repair_extraction', agent_task={'prompt': str(ROOT / 'prompts/reconcile.md'), 'reason': str(exc)})
    checkpoint_hash = fingerprint(parts)
    receipt_path = run / 'reconciliation.json'
    receipt = read(receipt_path) if receipt_path.exists() else {}
    if reconciled:
        receipt = {'schema_version': VERSION, 'checkpoint_hash': checkpoint_hash}
        write(receipt_path, receipt)
    if receipt != {'schema_version': VERSION, 'checkpoint_hash': checkpoint_hash}:
        return response('reconcile', agent_task={'prompt': str(ROOT / 'prompts/reconcile.md'), 'checkpoint_hash': checkpoint_hash})
    ir = assemble(run)
    assessment = None
    assessment_path = run / 'discovery-assessment.json'
    if assessment_path.exists():
        assessment = read(assessment_path)
        validate_schema(assessment, 'discovery-assessment')
        if assessment['ir_hash'] != fingerprint(ir):
            assessment = None
        else:
            require(all(set(item['unit_ids']) <= {u['unit_id'] for u in ir['units']} for item in assessment['weakly_supported']), 'Discovery assessment cites unknown units')
    if assessment and assessment['no_capability_reason'].strip():
        return response('no_supported_capabilities', summary=summary(docs, ir),
                        message=assessment['no_capability_reason'], weakly_supported=assessment['weakly_supported'])
    if not (run / 'capabilities.json').exists():
        return response('discover', summary=summary(docs, ir), agent_task={'prompt': str(ROOT / 'prompts/discover-capabilities.md'),
                        'ir': str(run / 'ir.json'), 'ir_hash': fingerprint(ir), 'destination': str(run / 'capabilities.json')})
    try:
        caps = validate_capabilities(run)
    except (Invalid, ValueError, OSError) as exc:
        return response('discover', summary=summary(docs, ir), agent_task={'prompt': str(ROOT / 'prompts/discover-capabilities.md'),
                        'ir_hash': fingerprint(ir), 'destination': str(run / 'capabilities.json'), 'reason': str(exc)})
    def capability_summary():
        result = summary(docs, ir, caps)
        if assessment: result['weakly_supported'] = assessment['weakly_supported']
        return result

    presentation_path = run / 'presentation.json'
    presentation = {'ir_hash': fingerprint(ir), 'capabilities_hash': fingerprint(caps),
                    'choices': [c['capability_id'] for c in caps['capabilities']]}
    prior = read(presentation_path) if presentation_path.exists() else None
    if select and str(select).isdigit():
        if prior != presentation:
            write(presentation_path, presentation)
            session['pending_request'].update(intent='compile', select=None, build_all=False)
            write(session_path, session)
            return response('choose', summary=capability_summary(), message='The options have changed. Choose from this current list before I build one.')
        number = int(select)
        require(1 <= number <= len(presentation['choices']), 'Capability number is outside the displayed options')
        select = presentation['choices'][number-1]
    write(presentation_path, presentation)
    chosen = []
    if build_all:
        chosen = caps['capabilities']
    elif select:
        chosen = [c for c in caps['capabilities'] if str(select).casefold() in {c['capability_id'].casefold(), c['title'].casefold()}]
        require(len(chosen) == 1, 'That capability does not match a current option; resolve its name conversationally')
    elif intent in {'build', 'use', 'compare'}:
        previous = session.get('last_built', {})
        if intent in {'use', 'compare'} and recorded_is_active(previous.get('run')):
            chosen = [c for c in caps['capabilities'] if c['capability_id'] == previous.get('capability_id')]
        if not chosen and len(caps['capabilities']) == 1: chosen = caps['capabilities']
    if not chosen:
        return response('choose', summary=capability_summary(), message='Here are the most useful capabilities this material supports. Which should I build?')

    built = []
    for cap in chosen:
        build_key = fingerprint({'ir': fingerprint(ir), 'capability': cap, 'renderer': digest((ROOT / 'scripts/ec.py').read_bytes()),
                                 'schemas': {p.name: digest(p.read_bytes()) for p in sorted((ROOT / 'schemas').glob('*.json'))}})
        destination = home / 'capabilities' / build_key[:16] / cap['capability_id']
        if destination.exists():
            manifest = validate_package(destination)
            require(manifest['ir_hash'] == fingerprint(ir) and read(destination / 'capability.json') == cap, 'Saved capability differs from its build identity')
        else:
            package(run, cap['capability_id'], destination)
        built.append({'id': cap['capability_id'], 'title': cap['title'], 'location': str(destination),
                      'skill': str(destination / 'SKILL.md'), 'can_do': cap['description'],
                      'limitations': cap['boundaries'], 'disagreements': cap['conflict_policy']})
    if len(built) == 1:
        session['last_built'] = {'run': session['active_run'], 'capability_id': built[0]['id']}
        write(session_path, session)
    result = response('use' if intent == 'use' else 'ready', summary=capability_summary(), built=built)
    result['guidance'] = str(ROOT / 'prompts/guide-use.md')
    if intent == 'compare':
        require(len(built) == 1, 'Compare one capability at a time')
        task_path = (project / tasks).resolve() if tasks else run / 'evaluation/tasks.json'
        rubric_path = (project / rubric).resolve() if rubric else run / 'evaluation/rubric.json'
        if not task_path.exists() or not rubric_path.exists():
            return {**result, 'phase': 'prepare_evaluation', 'agent_task': {'prompt': str(ROOT / 'prompts/evaluate.md'),
                    'tasks_destination': str(task_path), 'rubric_destination': str(rubric_path)}}
        from evaluate import prepare_comparison
        evaluation_id = fingerprint({'ir': fingerprint(ir), 'capability': read(Path(built[0]['location']) / 'capability.json'),
                                     'tasks': read(task_path), 'rubric': read(rubric_path)})[:16]
        destination = home / 'evaluations' / f'{built[0]["id"]}-{evaluation_id}'
        prepare_comparison(run, built[0]['location'], destination, task_path, rubric_path)
        result.update(phase='evaluate', evaluation=str(destination), agent_task={'prompt': str(ROOT / 'prompts/evaluate.md')})
    return result
