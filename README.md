# operation (ApiAgentService1)

A simple API that adds two numbers (`a + b`). It also ships a typed Python client (`operation.OperationClient`) for downstream consumers.

## Run

```sh
uv sync
uv run uvicorn operation.app:app --port 8001 --reload
```

Interactive docs: http://localhost:8001/docs. OpenAPI contract: http://localhost:8001/openapi.json

## API

| Method | Path                       | Body               | Response            |
|--------|----------------------------|--------------------|---------------------|
| POST   | `/v1/operation/numeric_op` | `{"a": 2, "b": 3}` | `{"result": 5.0}`   |
| GET    | `/health`                  |                    | `{"status": "ok"}`  |

The result is `a + b`. Missing or non-numeric inputs return `422`.

```sh
curl -X POST localhost:8001/v1/operation/numeric_op -H 'content-type: application/json' -d '{"a":2,"b":3}'
```

## Client usage

```python
from operation import OperationClient

with OperationClient("http://localhost:8001") as op:
    op.numeric_op(2, 3).result  # 5.0
```

## Test

```sh
uv run pytest
```

## Service1 change agent

On every push to `main`, including merged PRs, [change-agent.yml](.github/workflows/change-agent.yml) runs `agent/change_agent.py`. The agent uses an LLM on NVIDIA NIM to summarize the diff and flag changes to the public contract. It then sends that message to the ApiAgentService2 agent as a `service1-changed` [repository_dispatch](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event) event.

### Setup

Add these under **Settings → Secrets and variables → Actions**:

| Name | Type | Value |
|------|------|-------|
| `NVIDIA_API_KEY` | Secret | Your NVIDIA NIM API key |
| `SERVICE2_DISPATCH_TOKEN` | Secret | Fine-grained personal access token with access to only `prangunj23/ApiAgentService2` and **Contents: Read and write** |
| `NIM_MODEL` | Variable or secret | Optional. Default: `moonshotai/kimi-k3` |

### Try it locally

This prints the message without sending it:

```sh
NVIDIA_API_KEY=... uv run agent/change_agent.py --dry-run --before <sha> --after <sha>
```

## Chat agent

`chat_agent/` holds a chat agent for this repo, built on agentkit. A copy of agentkit is vendored at `chat_agent/vendor/agentkit/` and committed here, so this repo installs, tests, and deploys with nothing else checked out beside it. The copy is generated from the ApiAgentKit repo — change agentkit there and re-run its `scripts/sync_vendor.py`, never edit `vendor/` directly, because the next sync overwrites it. CI runs `vendor/check_vendor.py` to enforce that. You talk to the agent in the ApiAgentUI app. It works in its own clone of this repo under `~/.apiagent/service1/`, so it never touches your checkout. It can:
- read the code
- edit `src/` and `tests/`
- run the tests
- open pull requests
- message the ApiAgentService2 agent
- send the same `service1-changed` event as the workflow above, using `notify_service2`

You approve pull requests and events in the UI before they happen.

```sh
cd chat_agent
cp .env.example .env   # add NVIDIA_API_KEY and GITHUB_TOKEN
uv sync
uv run pytest
```

To run this agent on its own, from `chat_agent/`:

```sh
uv run agentkit serve service1_agent.spec:SPEC --port 9001
```

To run it alongside the other agents during development, from this repo's root (needs the sibling checkouts):

```sh
uv run --project ../ApiAgentKit agentkit dev --registry ../ApiAgentUI/public/registry.json
```

## Deploy

This repo deploys to its own Oracle Always Free VM, with nothing else checked out beside it. `deploy/bootstrap.sh` provisions the VM and doubles as the deploy command; `operation.service` and `service1-agent.service` run the API and the chat agent. Both bind to Tailscale rather than the public interface, so no port is ever opened in OCI.

See [deploy/README.md](deploy/README.md) for the runbook.
