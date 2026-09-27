"""Authored language observations through the normal workflow and pack boundary.

No model is called: these checks establish preservation, not extraction accuracy.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from goal_workflow import work, validate_build
from packs import build_pack, install_pack, open_pack


class LanguagePatternTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'author'
        self.project.mkdir()
        isolate_home(self, self.base)

    def prepare(self):
        brief = {
            'schema_version': '1.0', 'intent': 'reference',
            'intent_reason': 'Inspect wording separately from topic knowledge.',
            'objective': 'Describe Ari wording patterns and situation limits.',
            'context': 'PRIVATE-CONTEXT-SENTINEL',
            'constraints': ['Exclude Blake wording and beliefs.'],
            'work': {'label': 'Task', 'text': ''},
            'desired_result': 'Language patterns',
            'success_criteria': ['Preserve exact examples, speakers and register differences.'],
        }
        brief_path = self.project / 'brief.json'
        ec.write(brief_path, brief)
        result = work(project=self.project, input=str(ec.ROOT / 'fixtures/language-patterns'),
                      name='Language examples', brief=str(brief_path))
        corpus, docs, _ = ec.validate_sources(result['run'])
        by_name = {d['filename']: d for d in docs.values()}

        def unit(uid, title, statement, scope, examples, speaker='Ari', status='inferred'):
            evidence = []
            for filename, quote in examples:
                doc = by_name[filename]
                segment = next(s for s in doc['segments'] if quote in s['text'])
                self.assertEqual(segment['speaker'], speaker)
                evidence.append({'source_id': doc['source_id'],
                                 'segment_id': segment['segment_id'], 'quote': quote})
            return {'schema_version': '1.0', 'unit_id': uid, 'type': 'claim',
                    'status': status, 'title': title, 'statement': statement,
                    'scope': scope, 'derivation': 'Authored interpretation of this synthetic sample.' if status == 'inferred' else '',
                    'evidence': evidence,
                    'attribution': [{'source_id': e['source_id'], 'name': speaker}
                                    for e in {e['source_id']: e for e in evidence}.values()],
                    'relations': []}

        patterns = [
            unit('ari-confirmation', 'Qualified practical questions',
                 'Two distinct questions open with Just to confirm and ask about concrete booking details.',
                 'Ari in the supplied ordinary conversation only; not an always rule.',
                 [('conversation.vtt', 'Just to confirm, does the booking include the room?'),
                  ('conversation.vtt', 'Just to confirm, is the equipment fee a separate charge?')]),
            unit('ari-administrative-words', 'Administrative vocabulary',
                 'Booking, equipment fee, separate charge and approval name practical administrative details.',
                 'Ari in this booking discussion; no claim of vocabulary unique to this speaker.',
                 [('conversation.vtt', 'Just to confirm, does the booking include the room?'),
                  ('conversation.vtt', 'Just to confirm, is the equipment fee a separate charge?'),
                  ('conversation.vtt', 'In practical terms, we need approval before we pay the fee.')]),
            unit('ari-urgent-instructions', 'Direct urgent instructions',
                 'The announcement uses short imperatives without the conversational opening.',
                 'Ari in this urgent announcement; text does not establish vocal delivery.',
                 [('announcement.vtt', 'Leave the room now. Use the marked exit.')]),
            unit('blake-word-preference', 'Guest stated preference',
                 'Blake says a booking is called an extravaganza.',
                 'Blake only; this statement does not establish Ari vocabulary.',
                 [('conversation.vtt', 'I always call a booking an extravaganza.')],
                 speaker='Blake', status='explicit'),
        ]
        self.patterns = patterns
        for doc in docs.values():
            selected = [u for u in patterns if u['evidence'][0]['source_id'] == doc['source_id']]
            ec.write(Path(result['run']) / 'units' / (doc['source_id'] + '.json'), {
                'schema_version': '1.0', 'corpus_id': corpus['corpus_id'],
                'source_id': doc['source_id'], 'units': selected,
                'note': 'Authored semantic checkpoint; README is fixture context, not speaker evidence.',
            })
        return work(project=self.project, reconciled=True)

    def test_language_profile_survives_pack_install_without_importing_guest_preferences(self):
        result = self.prepare()
        self.assertEqual(result['phase'], 'assess_coverage')
        task = result['agent_task']
        draft = Path(task['draft'])
        selected = [u for u in self.patterns if u['unit_id'].startswith('ari-')]
        ids = [u['unit_id'] for u in selected]
        ec.write(draft / 'coverage.json', {
            'schema_version': '1.0', 'brief_id': task['brief_id'], 'ir_hash': task['ir_hash'],
            'decision': 'reuse', 'source_ids': [], 'reason': 'Authored language observations cover the request.', 'unsupported': [],
        })
        self.assertEqual(work(project=self.project)['phase'], 'design_method')
        cap = {'schema_version': '1.0', 'capability_id': 'ari-language',
               'title': 'Ari language patterns', 'description': 'Inspect language in the fictional sample.',
               'rationale': 'Keep language observations selectable independently of guest preferences.',
               'inputs': 'A new text and its intended situation.',
               'output_contract': 'Wording suggestions with original meaning preserved.', 'unit_ids': ids,
               'steps': [{'instruction': u['statement'], 'unit_ids': [u['unit_id']]} for u in selected],
               'boundaries': [u['scope'] for u in selected],
               'conflict_policy': 'Urgent instructions need not use ordinary conversational qualifiers.',
               'checks': ['Keep Blake preferences out of Ari wording guidance.', 'Preserve facts and intended meaning.'],
               'examples': [{'input': 'Ask whether a fictional library reservation includes a key.',
                             'output': 'Just to confirm, does the reservation include the key?',
                             'unit_ids': ['ari-confirmation'], 'status': 'synthetic'}]}
        method = {'schema_version': '1.0', 'brief_id': task['brief_id'], 'ir_hash': task['ir_hash'], 'capability': cap}
        ec.write(draft / 'method.json', method)
        applied = work(project=self.project)
        self.assertEqual(applied['phase'], 'apply_method')
        ec.write(draft / 'result.json', {
            'schema_version': '1.1', 'brief_id': task['brief_id'], 'ir_hash': task['ir_hash'],
            'method_hash': applied['agent_task']['method_hash'], 'target': 'reference',
            'summary': 'Authored language profile with register limits.',
            'sections': [{'kind': 'answer', 'title': u['title'], 'content': u['statement'],
                          'status': 'inferred', 'unit_ids': [u['unit_id']]} for u in selected],
            'disagreements': [], 'limitations': ['Authored fixture; no model effectiveness evaluation.'],
            'unsupported': [], 'additional_general_advice': [],
        })
        self.assertEqual(work(project=self.project)['phase'], 'review_result')
        done = work(project=self.project, reviewed=True)
        self.assertEqual(done['phase'], 'complete')
        self.assertTrue(validate_build(done['build'])['valid'])
        exported = build_pack(self.project, 'Language examples', self.base / 'language.lectic', include_sources=True)
        manifest, members = open_pack(Path(exported['pack']).read_bytes())
        method_path = f"methods/{manifest['methods'][0]['build_id']}/method.json"
        self.assertEqual(json.loads(members[method_path]), cap)
        self.assertNotIn('blake-word-preference', json.loads(members[method_path])['unit_ids'])
        self.assertFalse(any(b'PRIVATE-CONTEXT-SENTINEL' in raw for raw in members.values()))
        self.assertFalse(any(path.endswith('brief.json') for path in members))
        receiver = self.base / 'receiver'
        receiver.mkdir()
        isolate_home(self, self.base, 'receiver-home')
        installed = install_pack(receiver, exported['pack'])
        self.assertEqual(installed['verification'], 'verified')
        self.assertTrue(installed['knowledge_matches_pack'])
        from collection_store import Library
        library = Library(receiver)
        folder, data = library.resolve('Language examples')
        ir = ec.validate_ir(library.run(folder, data))
        self.assertEqual({u['unit_id']: u for u in ir['units']}, {u['unit_id']: u for u in self.patterns})
        self.assertEqual(ec.read(folder / 'pack' / method_path), cap)
        _, docs, _ = ec.validate_sources(library.run(folder, data))
        conversation = next(d for d in docs.values() if d['filename'] == 'conversation.vtt')
        self.assertEqual([s['speaker'] for s in conversation['segments']], ['Ari', 'Blake', 'Ari', 'Blake', 'Ari'])

    def test_paraphrased_wording_cannot_replace_exact_pattern_evidence(self):
        result = self.prepare()
        _, docs, segments = ec.validate_sources(result['run'])
        changed = copy.deepcopy(self.patterns[0])
        changed['evidence'][0]['quote'] = 'Just to check, does the booking include the room?'
        with self.assertRaises(ec.Invalid):
            ec.validate_units([changed], docs, segments, check_relations=False)


if __name__ == '__main__':
    unittest.main()
