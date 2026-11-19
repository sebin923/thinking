import importlib.util
import io
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('remote_check', Path(__file__).parents[1] / 'check_remote_llm.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_no_credentials_means_no_request(monkeypatch):
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('No network without credentials'))
    with pytest.raises(ValueError):
        module.check('http://gpu.example:8001', '')


def test_generation_authenticates_and_checks_selected_identity(monkeypatch):
    calls = []
    def respond(req, **kwargs):
        calls.append(req)
        assert dict((k.lower(), v) for k, v in req.header_items())['x-llm-token'] == 'test-only'
        value = {'status': 'ok', 'loaded': False, 'structured_mode': 'base'} if req.data is None else {
            'content': '확인한 기록만 작성했다.',
            'loaded_identity': {'profile': 'curated_over1000_20261119', 'adapter_sha256': 'expected'}}
        return io.BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(module.urllib.request, 'urlopen', respond)
    result = module.check('http://gpu.example:8001', 'test-only', generate=True, expected_sha='expected')
    assert result['generation_checked'] and len(calls) == 2
    assert calls[1].get_method() == 'POST'


def test_different_model_cannot_be_reported_as_selected(monkeypatch):
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(json.dumps({
        'status': 'ok', 'loaded': True, 'loaded_identity': {'adapter_sha256': 'other'}}).encode()))
    with pytest.raises(ValueError, match='verify'):
        module.check('http://gpu.example:8001', 'test-only', expected_sha='expected')
