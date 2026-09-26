"""Grounding and bounded failure checks; fixture prose is not a model-quality evaluation."""
import copy

import pytest

from lectic.cloud.suggestions import discover


class Model:
    last_model = 'fixture'

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def json(self, purpose, payload, schema):
        self.calls.append(payload)
        return next(self.responses)


def suggestion():
    return {'summary': 'Start with a small test so you can compare the result.', 'ideas': [{
        'title': 'Test one suspected cause', 'description': 'Make the failure easier to reproduce before changing anything.',
        'format': 'Checklist', 'brief': 'Create a checklist for reproducing this failure.', 'unit_ids': ['debug-1']}]}


def test_one_supported_idea_does_not_need_padding():
    model = Model([suggestion()])
    result = discover('Debugging', {'units': [{'unit_id': 'debug-1'}]}, model, 'I am preparing a release.')
    assert len(result['ideas']) == 1
    assert result['context'] == 'I am preparing a release.'
    assert model.calls[0]['person_context'] == result['context']
    assert len(model.calls) == 1


def test_unavailable_evidence_is_repaired_without_losing_user_context():
    invalid = copy.deepcopy(suggestion())
    invalid['ideas'][0]['unit_ids'] = ['invented']
    model = Model([invalid, suggestion()])
    result = discover('Debugging', {'units': [{'unit_id': 'debug-1'}]}, model, 'My release is tomorrow.')
    assert result['ideas'][0]['unit_ids'] == ['debug-1']
    assert len(model.calls) == 2
    assert model.calls[1]['repair']
    assert model.calls[1]['person_context'] == model.calls[0]['person_context']


def test_empty_knowledge_does_not_spend_on_suggestions():
    model = Model([])
    with pytest.raises(ValueError, match='no processed knowledge'):
        discover('Unread source', {'units': []}, model)
    assert model.calls == []


def test_invalid_suggestions_stop_after_bounded_retry():
    invalid = suggestion()
    invalid['ideas'] = []
    model = Model([invalid, invalid])
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        discover('Debugging', {'units': [{'unit_id': 'debug-1'}]}, model)
    assert len(model.calls) == 2
