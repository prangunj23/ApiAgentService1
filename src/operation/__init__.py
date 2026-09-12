"""operation: adds two numbers. Exposes the API models and a typed client for consumers."""

from operation.client import OperationClient
from operation.models import NumericOpRequest, NumericOpResponse

__all__ = ["NumericOpRequest", "NumericOpResponse", "OperationClient"]
