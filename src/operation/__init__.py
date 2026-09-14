"""operation: multiplies two numbers (a * b). Exposes the API models and a typed client for consumers."""

from operation.client import OperationClient
from operation.models import NumericOpRequest, NumericOpResponse

__all__ = ["NumericOpRequest", "NumericOpResponse", "OperationClient"]
