"""외부 통신이나 GPU 가중치 로딩 없이 백엔드와 GPU API의 개인화 선택을 검증한다."""
from contextlib import nullcontext
import json
import sys
from types import ModuleType, SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
import requests

from test_qwen_features import api, document, reply
server = pytest.importorskip("common_llm", reason="GPU PC 전용 코드가 없는 웹 체크아웃입니다.")
from main import app
import models
from routers.auth import get_current_user


@pytest.fixture
def gpu(monkeypatch, tmp_path):
    class FakeInput:
        shape = (1, 3)

        def to(self, device):
            return self

    class FakePeftModel:
        def __init__(self):
            self.peft_config = {'common': {}}
            self.active_adapter = 'common'
            self.loaded = []
            self.generation_config = SimpleNamespace(eos_token_id=[99])

        def load_adapter(self, path, adapter_name, is_trainable=False):
            assert not is_trainable
            assert path == str(tmp_path / adapter_name)
            self.peft_config[adapter_name] = {}
            self.loaded.append(adapter_name)

        def set_adapter(self, name):
            assert name in self.peft_config
            self.active_adapter = name

        def eval(self):
            pass

        def generate(self, **kwargs):
            return [[1, 2, 3, 77, 99]]

    model = FakePeftModel()

    class FakeTokenizer:
        pad_token_id = 0
        eos_token_id = 99

        def __call__(self, *args, **kwargs):
            return {'input_ids': FakeInput()}

        def get_vocab(self):
            return {'<|im_end|>': 99}

        def decode(self, *args, **kwargs):
            return f'{model.active_adapter} 모델로 확인한 사실을 작성했습니다.'

    peft = ModuleType('peft')
    peft.PeftModel = FakePeftModel
    monkeypatch.setitem(sys.modules, 'peft', peft)
    monkeypatch.setattr(server, 'PERSONAL_ROOT', tmp_path)
    monkeypatch.setattr(server, 'TOKEN', 'test-qwen-token')
    monkeypatch.setattr(server, '_model', model)
    monkeypatch.setattr(server, '_torch', SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setattr(server, '_processor', SimpleNamespace(
        tokenizer=FakeTokenizer(), apply_chat_template=lambda *a, **k: 'encoded prompt'))
    monkeypatch.setattr(server, 'load_model', lambda: None)
    monkeypatch.setattr(server, 'selected_profile', lambda: 'legacy')

    def publish(user_id, *, weights=True, base=None):
        folder = tmp_path / f'user_{user_id}'
        folder.mkdir(exist_ok=True)
        (folder / 'adapter_config.json').write_text(
            json.dumps({'base_model_name_or_path': base or server.MODEL_ID}), encoding='utf-8')
        if weights:
            # 가중치를 실제로 읽지 않고 모의 PEFT 모델로 선택과 계정 분리를 검증한다.
            (folder / 'adapter_model.safetensors').write_bytes(b'test weights')

    with TestClient(server.app) as client:
        yield client, model, publish


def bridge(post, gpu_client):
    def request(url, *, json, headers, timeout):
        assert url == 'http://qwen.test:8001/draft'
        return gpu_client.post('/draft', json=json, headers=headers)
    post.side_effect = request


def test_ready_personal_adapter_is_used_without_a_selector(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    publish(1)
    bridge(post, gpu_client)
    doc = document(client)
    result = client.post(f'/api/documents/{doc["id"]}/draft-ai', json={'user_id': 2}).json()
    assert result['personalized'] is True
    assert result['personalization_type'] == 'adapter'
    assert result['content'].startswith('user_1')
    assert result['usage']['used'] == 1
    assert post.call_count == 1
    assert post.call_args.kwargs['json']['user_id'] == 1
    assert model.loaded == ['user_1']


def test_missing_adapter_falls_back_with_saved_preferences_and_charges_once(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    bridge(post, gpu_client)
    client.put('/api/writing/preferences', json={'preferred_tone': 'formal', 'sentence_length': 'short'})
    doc = document(client)
    response = client.post(f'/api/documents/{doc["id"]}/draft-ai')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['personalized'] is False
    assert result['personalization_type'] == 'preference_prompt'
    assert result['content'].startswith('common')
    assert result['usage']['used'] == 1
    payloads = [call.kwargs['json'] for call in post.call_args_list]
    assert [p['mode'] for p in payloads] == ['personal', 'common']
    assert payloads[0]['user_preferences'] == payloads[1]['user_preferences']
    assert payloads[1]['user_preferences']['sentence_length'] == 'short'
    assert model.loaded == []


def test_newly_available_adapter_is_detected_on_the_next_request(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    bridge(post, gpu_client)
    doc = document(client)
    assert client.post(f'/api/documents/{doc["id"]}/draft-ai').json()['personalized'] is False
    publish(1)
    result = client.post(f'/api/documents/{doc["id"]}/draft-ai').json()
    assert result['personalized'] is True
    assert result['usage']['used'] == 2
    assert post.call_count == 3


def test_another_account_never_reuses_the_previous_personal_adapter(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    publish(1)
    bridge(post, gpu_client)
    first = document(client)
    assert client.post(f'/api/documents/{first["id"]}/draft-ai').json()['personalized'] is True
    other = db.get(models.User, 2)
    app.dependency_overrides[get_current_user] = lambda: other
    second = document(client)
    response = client.post(f'/api/documents/{second["id"]}/draft-ai').json()
    assert response['personalized'] is False
    assert response['content'].startswith('common')
    assert all(call.kwargs['json']['user_id'] == 2 for call in post.call_args_list[1:])
    assert model.active_adapter == 'common'


def test_two_ready_accounts_load_only_their_own_adapters(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    publish(1)
    publish(2)
    bridge(post, gpu_client)
    first = document(client)
    assert client.post(f'/api/documents/{first["id"]}/draft-ai').json()['content'].startswith('user_1')
    other = db.get(models.User, 2)
    app.dependency_overrides[get_current_user] = lambda: other
    second = document(client)
    assert client.post(f'/api/documents/{second["id"]}/draft-ai').json()['content'].startswith('user_2')
    assert model.loaded == ['user_1', 'user_2']


def test_config_without_weights_is_not_treated_as_a_completed_model(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    publish(1, weights=False)
    bridge(post, gpu_client)
    doc = document(client)
    result = client.post(f'/api/documents/{doc["id"]}/draft-ai').json()
    assert result['personalized'] is False and model.loaded == []


@pytest.mark.parametrize('failure, expected', [('timeout', 504), ('unavailable', 503), ('invalid_config', 422)])
def test_auto_selection_does_not_hide_errors_or_spend_quota(api, gpu, failure, expected):
    client, db, post = api
    gpu_client, model, publish = gpu
    doc = document(client)
    if failure == 'timeout':
        post.side_effect = requests.Timeout()
    elif failure == 'unavailable':
        from unittest.mock import Mock
        post.return_value = Mock(status_code=503)
    else:
        publish(1, base='different/base-model')
        bridge(post, gpu_client)
    response = client.post(f'/api/documents/{doc["id"]}/draft-ai')
    assert response.status_code == expected, response.text
    assert post.call_count == 1
    assert client.get('/api/ai-usage/today').json()['used'] == 0


def test_unapplied_personal_model_is_an_error_not_silent_common_success(api):
    client, db, post = api
    doc = document(client)
    reply(post, '기본 모델 응답', personalized=False)
    assert client.post(f'/api/documents/{doc["id"]}/draft-ai').status_code == 502
    assert post.call_count == 1
    assert client.get('/api/ai-usage/today').json()['used'] == 0


def test_explicit_common_request_remains_common_even_when_personal_is_ready(api, gpu):
    client, db, post = api
    gpu_client, model, publish = gpu
    publish(1)
    bridge(post, gpu_client)
    doc = document(client)
    result = client.post(f'/api/documents/{doc["id"]}/draft-common-ai').json()
    assert result['personalized'] is False
    assert result['personalization_type'] == 'preference_prompt'
    assert post.call_count == 1 and model.loaded == []


@pytest.mark.parametrize('user_id', [None, 0, -1, True, '../user_2'])
def test_adapter_path_requires_a_real_positive_account_id(gpu, user_id):
    with pytest.raises(HTTPException) as error:
        server.personal_adapter_path(user_id)
    assert error.value.status_code == 400
