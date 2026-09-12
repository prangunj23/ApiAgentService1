from pydantic import BaseModel


class NumericOpRequest(BaseModel):
    a: float
    b: float


class NumericOpResponse(BaseModel):
    result: float
