"""Anthropic-protocol HTTP session provider.

For providers that implement the Anthropic /v1/messages API format,
such as Claude.ai API proxies, or compatible third-party services.
"""

import logging
import httpx
from history.store import HistoryStore, TopicHistory
from sessions.base import BaseSession

logger = logging.getLogger(__name__)


class AnthropicCompatSession(BaseSession):
    """Session for providers using the Anthropic /v1/messages API format.

    Auth: x-api-key header (standard Anthropic protocol).
    Response: parses content[0].text from the Anthropic response schema.
    """

    def __init__(
        self,
        history_store: HistoryStore,
        name: str,
        base_url: str,
        model: str,
        api_key: str,
        max_tokens: int = 8192,
    ):
        super().__init__(history_store)
        self.provider_name = name
        self.model = model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=300.0,
        )

    def _build_messages(self, history: TopicHistory) -> list[dict]:
        messages = []
        for msg in history.messages[-10:]:
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        return messages

    async def send(self, message: str, topic: str, timeout: int = 300) -> str:
        history = self.history_store.get_or_create(self.provider_name, topic)
        history.add("user", message)

        messages = self._build_messages(history)
        logger.info(f"[{self.provider_name}] POST /v1/messages model={self.model}")

        try:
            response = await self._client.post(
                "/v1/messages",
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
            reply = data["content"][0]["text"]

            history.add("assistant", reply)
            self.history_store.save(self.provider_name, topic)
            return reply

        except httpx.HTTPStatusError as e:
            error = f"Error: [{self.provider_name}] HTTP {e.response.status_code}"
            logger.error(error)
            return error
        except Exception as e:
            error = f"Error: [{self.provider_name}] {e}"
            logger.exception(f"[{self.provider_name}] Unexpected error")
            return error

    async def aclose(self) -> None:
        await self._client.aclose()
