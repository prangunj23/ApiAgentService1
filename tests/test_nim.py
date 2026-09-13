import httpx
import pytest

from agent import nim
from openai import APIConnectionError


class _FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise APIConnectionError(request=httpx.Request("POST", "https://example.test"))
        return type(
            "Completion",
            (),
            {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{"ok": true}'})()})()]},
        )()


def test_chat_json_retries_connection_error(monkeypatch: pytest.MonkeyPatch):
    fake_completions = _FakeCompletions()
    fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": fake_completions})()})()
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setattr(nim, "OpenAI", lambda **_kwargs: fake_client)
    monkeypatch.setattr(nim.time, "sleep", lambda _seconds: None)

    response = nim.chat_json("system", "user")

    assert response == {"ok": True}
    assert fake_completions.calls == 2
