"""Provider-contract tests with no network, database writes or billable requests."""
import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from models import NearbyAmenitiesIn, PriceAnalysisIn
from routes import ai


def invoke():
    return asyncio.run(ai.ai_nearby_amenities(NearbyAmenitiesIn(city='Port Moresby', suburb='Boroko')))


def provider(monkeypatch, content=None, status=200, stop='end_turn'):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'unit-test-key')
    response = httpx.Response(status, request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages'),
        json={'stop_reason': stop, 'content': [{'type': 'text', 'text': content or '{}'}]})
    post = AsyncMock(return_value=response)
    client = AsyncMock()
    client.__aenter__.return_value.post = post
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kwargs: client)
    return post


def test_direct_provider_contract_and_sanitization(monkeypatch):
    post = provider(monkeypatch, '```json\n' + json.dumps({'categories': [
        {'key': 'schools', 'label': 'Education', 'items': [{'name': 'Local school',
         'distance_hint': '~5 min drive', 'note': 'Visit https://example.com or +675 71234567'}]},
        {'key': 'unknown', 'items': [{'name': 'ignored'}]}, None]}) + '\n```')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'configured-model')
    result = invoke()
    assert result['location_label'] == 'Boroko, Port Moresby'
    assert len(result['categories']) == 1
    assert 'https://' not in result['categories'][0]['items'][0]['note']
    assert '71234567' not in result['categories'][0]['items'][0]['note']
    args, kwargs = post.call_args
    assert args == ('https://api.anthropic.com/v1/messages',)
    assert kwargs['headers']['x-api-key'] == 'unit-test-key'
    assert kwargs['json']['model'] == 'configured-model'
    assert kwargs['json']['messages'][0]['role'] == 'user'


def test_missing_key_is_clear_and_no_network(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kw: pytest.fail('Unexpected provider call'))
    with pytest.raises(HTTPException) as exc:
        invoke()
    assert exc.value.status_code == 503


@pytest.mark.parametrize('content,status,stop', [
    ('{}', 401, 'end_turn'), ('invalid json', 200, 'end_turn'),
    ('{"categories": []}', 200, 'max_tokens'), ('[]', 200, 'end_turn')])
def test_provider_failure_is_controlled(monkeypatch, content, status, stop):
    provider(monkeypatch, content, status, stop)
    with pytest.raises(HTTPException) as exc:
        invoke()
    assert exc.value.status_code == 502
    assert 'unit-test-key' not in exc.value.detail


def test_price_comparison_remains_key_independent(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    analyse = AsyncMock(return_value={'evidence_level': 'insufficient'})
    monkeypatch.setattr(ai.price_guidance, 'analyse', analyse)
    result = asyncio.run(ai.ai_price_analysis(PriceAnalysisIn(price=500000, city='Port Moresby', property_type='house', listing_type='sale')))
    assert result == {'evidence_level': 'insufficient'}
