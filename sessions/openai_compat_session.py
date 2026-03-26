"""OpenAI-compatible HTTP session provider (DeepSeek, Qianwen, etc.)."""

import logging
import httpx
from history.store import HistoryStore, TopicHistory
from sessions.api_session import APISession

logger = logging.getLogger(__name__)


class OpenAICompatSession(APISession):
    """Session for any provider with an OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        history_store: HistoryStore,
        name: str,
        base_url: str,
        model: str,
        api_key: str,
    ):
        super().__init__(history_store, base_url=base_url, api_key=api_key)
        self.provider_name = name
        self.model = model

    def _build_messages(self, history: TopicHistory) -> list[dict]:
        """Build OpenAI-format messages array from history (includes current message)."""
        messages = []
        for msg in history.messages[-10:]:
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        return messages

    async def send(self, message: str, topic: str, timeout: int = 300) -> str:
        """Send a message to the OpenAI-compatible endpoint and return the reply."""
        history = self.history_store.get_or_create(self.provider_name, topic)
        history.add("user", message)

        messages = self._build_messages(history)
        logger.info(f"[{self.provider_name}] POST /chat/completions model={self.model}")

        try:
            response = await self._client.post(
                "/chat/completions",
                json={"model": self.model, "messages": messages},
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]

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
