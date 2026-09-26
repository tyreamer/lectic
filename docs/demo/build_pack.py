"""Build and verify the site's authored, multi-source teaching pack.

Run from any folder with Python 3.10+ and Lectic's dependencies installed.
Only temporary Lectic homes are used. No retrieval or model calls are made.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from ec import VERSION, fingerprint, ingest, read, require, validate_sources, write, digest
from collection_store import Library
from goal_workflow import work
from packs import build_pack, install_pack, open_pack
from verify import verify_collection


def build():
    spec = read(Path(__file__).with_name('customer-discovery.json'))
    prior = os.environ.get('LECTIC_HOME')
    try:
        with tempfile.TemporaryDirectory(prefix='lectic-site-demo-') as temporary:
            project = Path(temporary)
            os.environ['LECTIC_HOME'] = str(project / 'author-home')
            inputs = project / 'inputs'
            inputs.mkdir()
            metadata = {}
            for source in spec['sources']:
                paragraphs = source['paragraphs']
                if source['filename'].endswith('.vtt'):
                    text = 'WEBVTT\n\n00:00.000 --> 00:15.000\n' + paragraphs[0] + '\n\n00:15.000 --> 00:30.000\n' + paragraphs[1] + '\n'
                elif source['filename'].endswith('.srt'):
                    text = '1\n00:00:00,000 --> 00:00:15,000\n' + paragraphs[0] + '\n\n2\n00:00:15,000 --> 00:00:30,000\n' + paragraphs[1] + '\n'
                else:
                    text = '\n\n'.join(paragraphs) + '\n'
                (inputs / source['filename']).write_text(text, encoding='utf-8')
                metadata[source['filename']] = {'title': source['title'], 'creator': 'Lectic authored teaching example', 'caption_type': 'synthetic'}
            metadata_path = project / 'metadata.json'
            write(metadata_path, metadata)
            run = project / 'run'
            ingest(inputs, run, metadata_path)
            corpus, docs, _ = validate_sources(run)
            for source in spec['sources']:
                sid, doc = next((sid, doc) for sid, doc in docs.items() if doc['filename'] == source['filename'])
                units = []
                for i, paragraph in enumerate(source['paragraphs'], 1):
                    segment = next(s for s in doc['segments'] if paragraph in s['text'])
                    units.append({'schema_version': VERSION, 'unit_id': f"{source['id']}-{i}", 'type': 'procedure',
                                  'status': 'explicit', 'title': paragraph.split('.')[0], 'statement': paragraph,
                                  'scope': 'Fictional customer-discovery teaching material authored for Lectic; not an effectiveness study.',
                                  'derivation': '', 'evidence': [{'source_id': sid, 'segment_id': segment['segment_id'], 'quote': paragraph}],
                                  'attribution': [{'source_id': sid, 'name': 'Lectic authored teaching example'}], 'relations': []})
                write(run / f'units/{sid}.json', {'schema_version': VERSION, 'corpus_id': corpus['corpus_id'], 'source_id': sid,
                                               'note': 'Authored checkpoints for the website example; not model-generated extraction.', 'units': units})
            Library(project).archive(adopt=run, name=spec['name'])
            work(project=project, collection=spec['name'], action='prepare', reconciled=True)
            brief = {'schema_version': VERSION, 'objective': 'Prepare a customer-discovery checklist',
                     'context': 'Authored website teaching example, not a live AI response.',
                     'constraints': ['Use only the six supplied fictional sources.'],
                     'work': {'label': 'Sample research plan', 'text': 'We plan to pitch the idea, gather compliments, and build after one interested response.'},
                     'desired_result': 'A checklist covering interviews, evidence review, and the next experiment.',
                     'success_criteria': ['Keep all recommendations traceable to the supplied source passages.']}
            brief_path = project / 'brief.json'
            write(brief_path, brief)
            task = work(project=project, collection=spec['name'], brief=str(brief_path), target='checklist')
            require(task['phase'] == 'assess_coverage', str(task))
            draft = Path(task['agent_task']['draft'])
            ir_hash = fingerprint(read(Path(task['run']) / 'ir.json'))
            brief_id = Path(task['agent_task']['brief']).stem
            all_units = [unit for step in spec['playbook'] for unit in step['unit_ids']]
            capability = {'schema_version': VERSION, 'capability_id': 'customer-discovery-playbook', 'title': 'Customer discovery playbook',
                          'description': 'Prepare an interview, compare observations, and design a next experiment using six saved sources.',
                          'rationale': 'Synthesizes complementary procedures from six authored examples into one reusable sequence.',
                          'inputs': 'A research question, participant context, observations, and the assumption to test.',
                          'output_contract': 'Return an interview plan, evidence-review checks, a next experiment, and source citations. Label this sequence as synthesized.',
                          'unit_ids': all_units,
                          'steps': [{'instruction': s['instruction'], 'unit_ids': s['unit_ids']} for s in spec['playbook']],
                          'boundaries': ['Fictional teaching sources do not establish commercial demand or effectiveness.', 'No sample size or conversion benchmark is established.'],
                          'conflict_policy': 'Keep contradictory observations and their contexts visible; do not treat a shared topic as agreement.',
                          'checks': ['Are observations separate from interpretations?', 'Is the next test tied to an assumption and observable outcome?'],
                          'examples': [{'input': 'Prepare a discovery session for a scheduling problem.',
                                        'output': 'Ask about the last scheduling difficulty, record the workaround, compare independent observations, and define one follow-up test. This is a synthesized teaching application.',
                                        'unit_ids': all_units, 'status': 'synthetic'}]}
            method = {'schema_version': VERSION, 'brief_id': brief_id, 'ir_hash': ir_hash, 'capability': capability}
            write(draft / 'coverage.json', {'schema_version': VERSION, 'brief_id': brief_id, 'ir_hash': ir_hash, 'decision': 'reuse',
                                           'source_ids': [], 'reason': 'All three checklist stages are covered by the twelve authored source procedures.',
                                           'unsupported': ['Commercial effectiveness and demand are not established.']})
            write(draft / 'method.json', method)
            write(draft / 'result.json', {'schema_version': VERSION, 'brief_id': brief_id, 'ir_hash': ir_hash, 'method_hash': fingerprint(method),
                                         'target': 'checklist', 'assessment': 'Learn from existing behavior, compare evidence, and define the next test.',
                                         'findings': [], 'proposed_revision': '\n'.join(s['instruction'] for s in spec['playbook']),
                                         'checklist': [{'action': s['instruction'], 'done_when': s['example'], 'unit_ids': s['unit_ids']} for s in spec['playbook']],
                                         'disagreements': [], 'limitations': ['Authored synthetic example, not live AI output or an independent effectiveness study.'],
                                         'unsupported': ['Proof of demand or a product recommendation.'], 'additional_general_advice': []})
            complete = work(project=project, collection=spec['name'], target='checklist', reviewed=True)
            require(complete['phase'] == 'complete', str(complete))
            destination = ROOT / 'docs/packs/customer-discovery.lectic'
            build_pack(project, spec['name'], destination, include_sources=True, version='1.0.0')
            manifest, _ = open_pack(destination.read_bytes())
            require(len(manifest['sources']) == 6 and manifest['unit_count'] == 12 and len(manifest['methods']) == 1, 'Unexpected pack contents')
            os.environ['LECTIC_HOME'] = str(project / 'recipient-home')
            installed = install_pack(project, str(destination), name=spec['name'])
            require(installed['verification'] == 'verified', str(installed))
            verified = verify_collection(project, spec['name'])
            require(verified['overall'] == 'verified', str(verified))
            info = {'file': 'packs/customer-discovery.lectic', 'name': spec['name'], 'version': manifest['version'],
                    'sources': 6, 'units': 12, 'methods': 1, 'bytes': destination.stat().st_size,
                    'sha256': digest(destination.read_bytes()), 'signature': 'unsigned authored teaching example',
                    'verification': installed['verification'], 'evidence': verified['overall']}
            write(Path(__file__).with_name('pack-info.json'), info)
            print(json.dumps(info, indent=2))
    finally:
        if prior is None:
            os.environ.pop('LECTIC_HOME', None)
        else:
            os.environ['LECTIC_HOME'] = prior


if __name__ == '__main__':
    build()
