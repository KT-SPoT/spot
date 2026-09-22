"""Common Scout interface.

Each owner may design the internal implementation freely.
The integration boundary is:
    SpotRequest -> ScoutResult v0.1
"""

from typing import Protocol

from src.contracts import ScoutResult, SpotRequest


class ScoutRunner(Protocol):
    def __call__(self, request: SpotRequest) -> ScoutResult: ...
