import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentkit.server import create_app
from agentkit.testing import FakeLLM, commit_files, git, http_factory_for, make_remote, make_settings, parse_sse
from agentkit.workspace import Repo
from service1_agent.spec import SPEC

# Keys that agent/change_agent.py puts in client_payload.
CHANGE_AGENT_PAYLOAD_KEYS = {"message", "summary", "contract_changes", "breaking", "before", "after", "compare_url", "commits"}


@pytest.fixture(autouse=True)
def no_dependency_installs(monkeypatch):
    monkeypatch.setattr(Repo, "uv_sync", lambda self: None)


def test_info_describes_the_agent(tmp_path):
    info = TestClient(create_app(SPEC, make_settings(tmp_path), llm=FakeLLM())).get("/api/info").json()
    assert info["id"] == "service1"
    assert info["repo"]["slug"] == "prangunj23/ApiAgentService1"
    assert [repo["slug"] for repo in info["reads"]] == ["prangunj23/ApiAgentService2"]
    assert next(tool for tool in info["tools"] if tool["name"] == "notify_service2")["needs_confirmation"] is True


def test_notify_service2_sends_the_change_agent_payload(tmp_path):
    origin = tmp_path / "origin"
    seed = make_remote(origin, "prangunj23/ApiAgentService1", {"README.md": "# operation\n"})
    make_remote(origin, "prangunj23/ApiAgentService2", {"README.md": "# consumer\n"})
    before = git(seed, "rev-parse", "HEAD")
    after = commit_files(seed, {"src/operation/app.py": "# renamed endpoint\n"}, "Rename numeric_op")

    dispatches = []

    def github(request: httpx.Request) -> httpx.Response:
        dispatches.append((request.url.path, json.loads(request.content)))
        return httpx.Response(204)

    factory = http_factory_for({}, fallback=lambda url: httpx.Client(base_url=url, transport=httpx.MockTransport(github)))
    call = {
        "summary": "Renamed numeric_op.",
        "message": "Update your client.",
        "breaking": True,
        "contract_changes": ["POST /v1/operation/numeric_op -> POST /v1/operation/subtract"],
    }
    llm = FakeLLM([{"tool_calls": [("notify_service2", call)]}, "Sent."])
    settings = make_settings(tmp_path / "data", git_base_url=str(origin), github_token="ghp_testtoken123")
    app = create_app(SPEC, settings, llm=llm, http_factory=factory)
    app.state.agent.workspace.ensure_cloned()
    client = TestClient(app)
    conversation_id = client.post("/api/conversations", json={}).json()["id"]

    events = parse_sse(client.post(f"/api/conversations/{conversation_id}/messages", json={"message": "Tell service2"}).text)
    assert events[-1]["type"] == "confirm_required" and after in events[-1]["action"]["preview"]
    assert dispatches == []

    parse_sse(client.post(f"/api/conversations/{conversation_id}/confirm", json={"approve": True}).text)
    [(path, body)] = dispatches
    assert path == "/repos/prangunj23/ApiAgentService2/dispatches"
    assert body["event_type"] == "service1-changed"
    payload = body["client_payload"]
    assert set(payload) == CHANGE_AGENT_PAYLOAD_KEYS
    assert (payload["before"], payload["after"], payload["breaking"]) == (before, after, True)
    assert payload["compare_url"] == f"https://github.com/prangunj23/ApiAgentService1/compare/{before}...{after}"
    assert "Rename numeric_op" in payload["commits"]

    [thread] = client.get("/api/conversations", params={"kind": "agent"}).json()
    assert (thread["channel"], thread["peer_agent"]) == ("github_dispatch", "service2")
    assert any(event["type"] == "dispatch_sent" for event in client.get("/api/events").json())
