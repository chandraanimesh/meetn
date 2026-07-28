from collections.abc import Mapping
from typing import Protocol


class LLMProviderPort(Protocol):
    async def decide(
        self,
        *,
        instructions: str,
        user_message: str,
        safe_context: Mapping[str, object],
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Return raw structured output for backend Pydantic validation."""
        ...
