"""An offline, explicitly authored example of first use and knowledge reuse.

This exercises real storage, evidence validation and result generation. Its
prewritten teaching example is not a live model result or effectiveness study.
"""
import os
from pathlib import Path
import tempfile

from ec import ROOT, VERSION, fingerprint, ingest, read, require, validate_sources, write
from collection_store import Library
from goal_workflow import work
from home import storage_root
from packs import build_pack, install_pack, open_pack
from store import home_transaction

NAME = 'Debugging Starter'
PACK_PATH = ROOT / 'fixtures/packs/debugging-starter.lectic'


def example_result(project, collection, *, second=False):
    """Apply the authored teaching method to one of two fixed sample plans."""
    brief = {'schema_version': '1.0', 'objective': 'Review the second sample plan' if second else 'Review a sample debugging plan',
             'context': 'Lectic offline starter. Prewritten synthetic example, not a live AI assessment.',
             'constraints': ['Use only the three cited debugging procedures.'],
             'work': {'label': 'Sample plan', 'text': ('I reproduced the bug and changed one variable. Ship after one passing example.' if second else
                      'Change the parser and delimiter settings together, then ship after one successful file.')},
             'desired_result': 'A repeatable debugging checklist' if second else 'A source-backed review of the sample plan',
             'success_criteria': ['Identify the missing check and give a concrete next action.']}
    brief_path = storage_root(project) / 'inbox' / ('starter-second.json' if second else 'starter-first.json')
    write(brief_path, brief)
    target = 'checklist' if second else 'review'
    result = work(project=project, collection=collection, brief=str(brief_path), target=target)
    if result['phase'] == 'complete': return result
    require(result['phase'] in {'assess_coverage', 'design_method', 'apply_method', 'review_result'},
            'Starter knowledge is not ready: ' + str(result))
    task = result['agent_task']
    draft = Path(task['draft'])
    run = Path(result['run'])
    ir = read(run / 'ir.json')
    brief_id = Path(task['brief']).stem
    ir_hash = fingerprint(ir)
    cap = next(c for c in read(ROOT / 'fixtures/demo_capabilities.json') if c['capability_id'] == 'debug-experiment-planner')
    require(set(cap['unit_ids']) <= {u['unit_id'] for u in ir['units']}, 'Starter units are missing')
    write(draft / 'coverage.json', {'schema_version': VERSION, 'brief_id': brief_id, 'ir_hash': ir_hash,
          'decision': 'reuse', 'source_ids': [], 'reason': 'The authored sample needs only these three saved procedures.',
          'unsupported': ['The sources do not diagnose the cause of this bug.']})
    method = {'schema_version': VERSION, 'brief_id': brief_id, 'ir_hash': ir_hash, 'capability': cap}
    write(draft / 'method.json', method)
    steps = [
        ('Record the smallest failing input, expected output and actual output before editing.', 'debug-reproduce'),
        ('Change one suspected cause, rerun the same input and revert an ineffective change.', 'debug-isolate'),
        ('Keep the original reproducer and check a nearby boundary before calling the bug fixed.', 'debug-regress'),
    ]
    findings = [{'title': 'One passing example is insufficient' if uid == 'debug-regress' else 'Make the experiment reproducible',
                 'priority': 'high', 'assessment': ('The second plan stops after one example.' if second else
                 'The sample plan changes two variables together and relies on one passing file.'),
                 'proposed_change': step, 'unit_ids': [uid]}
                for step, uid in (steps[-1:] if second else steps)]
    outcome = {'schema_version': VERSION, 'brief_id': brief_id, 'ir_hash': ir_hash, 'method_hash': fingerprint(method),
               'target': target, 'assessment': 'Add a boundary check before shipping.' if second else 'Use one controlled experiment at a time.',
               'findings': findings, 'proposed_revision': '\n'.join(step for step, _ in steps),
               'checklist': [{'action': step, 'done_when': 'The input and observed result are recorded.', 'unit_ids': [uid]} for step, uid in steps] if second else [],
               'disagreements': [], 'limitations': ['Prewritten synthetic teaching example. No model was called; effectiveness has not been independently tested.'],
               'unsupported': ['A diagnosis or guaranteed fix for a real bug.'], 'additional_general_advice': []}
    write(draft / 'result.json', outcome)
    completed = work(project=project, collection=collection, target=target, reviewed=True)
    require(completed['phase'] == 'complete', 'The starter result did not validate')
    return completed


@home_transaction
def try_starter(project='.'):
    manifest, _ = open_pack(PACK_PATH.read_bytes())
    library = Library(project)
    existing = next((entry for entry in library.index['collections'] if entry['name'] == NAME), None)
    if existing:
        folder, data = library.resolve(NAME)
        require(fingerprint(read(library.run(folder, data) / 'ir.json')) == manifest['ir_hash'],
                'Your Debugging Starter has changed. Keep it and install the bundled pack under another name to repeat the example.')
        collection = NAME
    else:
        installed = install_pack(project, str(PACK_PATH), name=NAME, pin=True)
        require(installed['verification'] == 'verified', 'Starter install is incomplete')
        collection = installed['collection']
    first = example_result(project, collection)
    second = example_result(project, collection, second=True)
    reuse = read(Path(second['build']) / 'validation.json')['reuse']
    return {'phase': 'starter_ready', 'collection': collection, 'first_result': first['result'],
            'second_result': second['result'], 'method': second['method'], 'reuse': reuse,
            'example_type': 'prewritten synthetic teaching example; no model call or independent quality evaluation',
            'next_prompt': 'Use my Debugging Starter to review this debugging plan: [paste your own plan]'}


def build_starter(destination=PACK_PATH):
    """Release maintainer operation: create the actual distributable from owned fixtures."""
    previous = os.environ.get('LECTIC_HOME')
    try:
        with tempfile.TemporaryDirectory(prefix='lectic-starter-build-') as temp:
            project = Path(temp)
            os.environ['LECTIC_HOME'] = str(project / 'home')
            run = project / 'authored-run'
            ingest(ROOT / 'fixtures/debugging', run)
            corpus, docs, _ = validate_sources(run)
            sid, doc = next(iter(docs.items()))
            units = []
            for spec in read(ROOT / 'fixtures/demo_knowledge.json'):
                if spec['filename'] != 'debugging.srt': continue
                segment = doc['segments'][spec['segment'] - 1]
                units.append({'schema_version': VERSION, 'unit_id': spec['unit_id'], 'type': spec['type'],
                    'status': 'explicit', 'title': spec['unit_id'].replace('-', ' ').capitalize(),
                    'statement': spec['statement'], 'scope': 'Synthetic debugging teaching transcript authored for Lectic.',
                    'derivation': '', 'evidence': [{'source_id': sid, 'segment_id': segment['segment_id'], 'quote': segment['text']}],
                    'attribution': [{'source_id': sid, 'name': 'Ada'}], 'relations': []})
            write(run / f'units/{sid}.json', {'schema_version': VERSION, 'corpus_id': corpus['corpus_id'],
                  'source_id': sid, 'note': 'Authored teaching checkpoint, not automatic extraction.', 'units': units})
            Library(project).archive(adopt=run, name=NAME)
            work(project=project, collection=NAME, action='prepare', reconciled=True)
            example_result(project, NAME)
            result = build_pack(project, NAME, destination, include_sources=True, version='1.0.0')
            return result
    finally:
        if previous is None: os.environ.pop('LECTIC_HOME', None)
        else: os.environ['LECTIC_HOME'] = previous


if __name__ == '__main__':
    import json
    print(json.dumps(build_starter(), indent=2))
