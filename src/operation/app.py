from fastapi import APIRouter, FastAPI

from operation.models import NumericOpRequest, NumericOpResponse

app = FastAPI(title="operation", version="1.0.0")

v1 = APIRouter(prefix="/v1/operation", tags=["operation"])


@v1.post("/numeric_op", response_model=NumericOpResponse)
def numeric_op(request: NumericOpRequest) -> NumericOpResponse:
    return NumericOpResponse(result=request.a + request.b)


app.include_router(v1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
