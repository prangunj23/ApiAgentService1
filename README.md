# operation (ApiAgentService1)

A simple API that adds two numbers. It also ships a typed Python client (`operation.OperationClient`) for downstream consumers.

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

Missing or non-numeric inputs return `422`.

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
