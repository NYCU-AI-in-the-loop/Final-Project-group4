import json
from types import SimpleNamespace

import pytest

from impactmap.predictor import predict, resolve_model, OffTopic
from impactmap.analyze import analyze
from test_analyze import repo  # noqa: F401


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ('AI_PROVIDER', 'OPENAI_MODEL', 'ANTHROPIC_MODEL', 'IMPACTMAP_MOCK',
                'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
        monkeypatch.delenv(key, raising=False)


def claude_client(payload, sent, stop='end_turn'):
    def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(stop_reason=stop, content=[
            SimpleNamespace(type='thinking'),
            SimpleNamespace(type='text', text='```json\n' + json.dumps(payload) + '\n```')])
    return SimpleNamespace(messages=SimpleNamespace(create=create))


PAYLOAD = {'off_topic': False, 'files': [
    {'path': 'api/auth.py', 'reason': 'Update auth', 'confidence': .9}]}


def test_claude_complete_report(repo):
    sent = {}
    client = claude_client(PAYLOAD, sent)
    report = analyze(repo, 'Add authentication', provider='claude',
                     predictor=lambda d, f, **kw: predict(d, f, client=client, **kw))
    assert report.provider == 'claude'
    assert report.model == 'claude-haiku-5-5'
    assert report.rows[0].risk == 'high'
    assert any(r.path == 'api/users.py' for r in report.rows)
    assert 'temperature' not in sent
    assert sent['max_tokens'] == 4096


def test_selection_precedence(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'claude')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'custom-claude')
    assert resolve_model() == ('claude', 'custom-claude')
    assert resolve_model('openai') == ('openai', 'gpt-6-luna')
    assert resolve_model('claude', 'override') == ('claude', 'override')
    with pytest.raises(ValueError):
        resolve_model('invalid')


@pytest.mark.parametrize('payload,stop', [(PAYLOAD, 'max_tokens'), ({'files': []}, 'end_turn'),
                                         ([], 'end_turn')])
def test_bad_claude_output_falls_back(payload, stop):
    result = predict('Update auth flow', ['api/auth.py'], provider='claude',
                     client=claude_client(payload, {}, stop))
    assert result.source == 'keyword'
    assert result.provider == 'claude'


def test_claude_off_topic():
    with pytest.raises(OffTopic):
        predict('Tell me a joke', ['api/auth.py'], provider='claude',
                client=claude_client({'off_topic': True, 'files': []}, {}))


def test_mock_does_not_call_provider(monkeypatch):
    monkeypatch.setenv('IMPACTMAP_MOCK', '1')
    monkeypatch.setenv('IMPACTMAP_MOCK_DELAY', '0')
    result = predict('Add password reset', ['backend/app/api/routes/login.py'], provider='claude')
    assert result.source == 'mock'
    assert result.provider == result.model == ''


def test_missing_key_fallback():
    result = predict('Update auth flow', ['api/auth.py'], provider='claude')
    assert result.source == 'keyword'


def test_ui_selection_and_result(monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *a, **k: None)
    from streamlit.testing.v1 import AppTest
    from impactmap import github
    import importlib
    module = importlib.import_module('impactmap.analyze')
    calls = []
    def fake_analyze(*args, **kwargs):
        calls.append(kwargs)
        return module.Report([], [], [], 'ai', provider=kwargs['provider'], model=kwargs['model'])
    monkeypatch.setattr(github, 'prepare', lambda url: ('.', [], []))
    monkeypatch.setattr(module, 'analyze', fake_analyze)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-placeholder')
    monkeypatch.setenv('IMPACTMAP_MOCK', '0')
    app = AppTest.from_file('../app.py').run()
    assert not app.exception
    app.selectbox[0].select('claude')
    app.text_area[0].input('Add authentication')
    app.button[0].click().run()
    assert not app.exception
    assert calls[0]['provider'] == 'claude'
    assert 'claude-haiku-5-5' in app.info[0].value
    app.selectbox[0].select('openai').run()
    assert len(calls) == 1
    assert 'claude-haiku-5-5' in app.info[0].value


def test_openai_request_uses_selected_model():
    sent = {}
    def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
            message=SimpleNamespace(content=json.dumps(PAYLOAD)))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = predict('Update auth flow', ['api/auth.py'], provider='openai', client=client)
    assert result.provider == 'openai'
    assert sent['model'] == 'gpt-6-luna'
    assert sent['reasoning_effort'] == 'none'
    assert 'temperature' not in sent


def test_ui_missing_key_and_mock(monkeypatch):
    import dotenv
    from impactmap import github
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *a, **k: None)
    monkeypatch.setattr(github, 'prepare', lambda url: ('.', [], []))
    app = AppTest.from_file('../app.py').run()
    app.selectbox[0].select('claude')
    app.text_area[0].input('Update auth flow')
    app.button[0].click().run()
    assert not app.exception
    assert 'ANTHROPIC_API_KEY' in app.error[0].value
    monkeypatch.setenv('IMPACTMAP_MOCK', '1')
    app.run()
    assert app.selectbox[0].disabled
    assert any('MOCK mode' in c.value for c in app.caption)


@pytest.mark.parametrize('configured_provider', ['gemini', '', '   '])
def test_ui_invalid_provider_defaults_to_openai(monkeypatch, configured_provider):
    import dotenv
    import importlib
    from impactmap import github
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *a, **k: None)
    monkeypatch.setattr(github, 'prepare', lambda url: ('.', [], []))
    monkeypatch.setenv('AI_PROVIDER', configured_provider)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-placeholder')
    module = importlib.import_module('impactmap.analyze')
    calls = []

    def fake_analyze(*args, **kwargs):
        calls.append(kwargs['provider'])
        return module.Report([], [], [], 'ai', provider=kwargs['provider'], model=kwargs['model'])

    monkeypatch.setattr(module, 'analyze', fake_analyze)
    app = AppTest.from_file('../app.py').run()
    assert not app.exception
    assert app.selectbox[0].value == 'openai'
    assert any('Invalid AI_PROVIDER' in w.value for w in app.warning)

    app.text_area[0].input('Update auth flow')
    app.button[0].click().run()
    assert not app.exception
    assert calls == ['openai']

    app.selectbox[0].select('claude')
    app.button[0].click().run()
    assert not app.exception
    assert calls == ['openai', 'claude']
