"""
Wrapper Magistral pour Strands — corrige le format streaming.

Les modèles Magistral (raisonnement) renvoient delta.content comme une liste
d'objets Pydantic (ThinkChunk / TextChunk) au lieu d'un simple str.
Ce wrapper :
  1. Filtre les thinking tokens (raisonnement interne)
  2. Extrait le texte des TextChunk
  3. Normalise en str pour Strands
"""
import logging
from collections.abc import AsyncGenerator
from typing import Any

import mistralai
from typing_extensions import override

from strands.models.mistral import MistralModel
from strands.models._validation import warn_on_tool_choice_not_supported
from strands.types.content import Messages
from strands.types.exceptions import ModelThrottledException
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

logger = logging.getLogger("kameleon.models.magistral")


def _extract_text(content: Any) -> str | None:
    """Extrait le texte visible d'un delta.content Magistral.

    - str → retourne tel quel
    - list d'objets Pydantic → filtre les ThinkChunk, extrait le texte des TextChunk
    - Retourne None si que du thinking (pas de texte à afficher)
    """
    if isinstance(content, str):
        return content if content else None

    if isinstance(content, list):
        parts = []
        for item in content:
            # Objet Pydantic avec .type
            if hasattr(item, "type"):
                if item.type == "text" and hasattr(item, "text"):
                    parts.append(item.text)
                # type == "thinking" → on skip (raisonnement interne)
            # Dict fallback
            elif isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        text = "".join(parts)
        return text if text else None

    return str(content) if content else None


class MagistralModel(MistralModel):
    """MistralModel avec support des modèles Magistral (raisonnement)."""

    def format_chunk(self, event: dict[str, Any]) -> StreamEvent:
        """Normalise le contenu avant de formater."""
        if event.get("chunk_type") == "content_delta" and event.get("data_type") == "text":
            raw_data = event["data"]
            text = _extract_text(raw_data)
            if text is None:
                text = ""
            if not isinstance(raw_data, str):
                logger.debug(
                    "format_chunk: normalized content_delta — raw_type=%s → text_len=%d",
                    type(raw_data).__name__, len(text),
                )
            event = {**event, "data": text}

        try:
            result = super().format_chunk(event)
        except Exception as exc:
            logger.exception(
                "format_chunk: super().format_chunk CRASHED — chunk_type=%s, data_type=%s, error=%s",
                event.get("chunk_type"), event.get("data_type"), exc,
            )
            raise

        # Double protection : s'assurer que le "text" dans contentBlockDelta
        # est toujours un str (Magistral peut renvoyer une liste dans certains
        # code paths internes de Strands event_loop).
        if isinstance(result, dict) and "contentBlockDelta" in result:
            delta = result["contentBlockDelta"].get("delta", {})
            if "text" in delta and not isinstance(delta["text"], str):
                logger.warning(
                    "format_chunk: DOUBLE PROTECTION triggered — text type=%s, value=%s",
                    type(delta["text"]).__name__, repr(delta["text"])[:200],
                )
                delta["text"] = _extract_text(delta["text"]) or ""

        return result

    @override
    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream avec filtrage des thinking tokens Magistral."""
        warn_on_tool_choice_not_supported(tool_choice)

        request = self.format_request(messages, tool_specs, system_prompt)

        logger.info("MagistralModel.stream() — model=%s, messages=%d, tools=%d",
                    request.get("model", "?"), len(request.get("messages", [])),
                    len(request.get("tools", []) or []))

        try:
            if not self.config.get("stream", True):
                logger.info("MagistralModel — non-streaming mode")
                async with mistralai.Mistral(**self.client_args) as client:
                    response = await client.chat.complete_async(**request)
                    for event in self._handle_non_streaming_response(response):
                        yield self.format_chunk(event)
                return

            async with mistralai.Mistral(**self.client_args) as client:
                stream_response = await client.chat.stream_async(**request)

                yield self.format_chunk({"chunk_type": "message_start"})

                content_started = False
                tool_calls: dict[str, list[Any]] = {}
                accumulated_text = ""

                async for chunk in stream_response:
                    if hasattr(chunk, "data") and hasattr(chunk.data, "choices") and chunk.data.choices:
                        choice = chunk.data.choices[0]

                        if hasattr(choice, "delta"):
                            delta = choice.delta

                            if hasattr(delta, "content") and delta.content:
                                # Extraire uniquement le texte visible (pas le thinking)
                                text = _extract_text(delta.content)

                                if text:
                                    if not content_started:
                                        yield self.format_chunk(
                                            {"chunk_type": "content_start", "data_type": "text"}
                                        )
                                        content_started = True

                                    yield self.format_chunk(
                                        {"chunk_type": "content_delta", "data_type": "text", "data": text}
                                    )
                                    accumulated_text += text

                            if hasattr(delta, "tool_calls") and delta.tool_calls:
                                for tool_call in delta.tool_calls:
                                    tool_id = tool_call.id
                                    tool_calls.setdefault(tool_id, []).append(tool_call)

                        if hasattr(choice, "finish_reason") and choice.finish_reason:
                            if content_started:
                                yield self.format_chunk(
                                    {"chunk_type": "content_stop", "data_type": "text"}
                                )

                            for tool_deltas in tool_calls.values():
                                yield self.format_chunk(
                                    {"chunk_type": "content_start", "data_type": "tool", "data": tool_deltas[0]}
                                )
                                for tool_delta in tool_deltas:
                                    if hasattr(tool_delta.function, "arguments"):
                                        yield self.format_chunk(
                                            {
                                                "chunk_type": "content_delta",
                                                "data_type": "tool",
                                                "data": tool_delta.function.arguments,
                                            }
                                        )
                                yield self.format_chunk({"chunk_type": "content_stop", "data_type": "tool"})

                            yield self.format_chunk(
                                {"chunk_type": "message_stop", "data": choice.finish_reason}
                            )

                            if hasattr(chunk, "usage"):
                                yield self.format_chunk({"chunk_type": "metadata", "data": chunk.usage})

        except Exception as e:
            logger.exception("MagistralModel.stream() EXCEPTION — type=%s, error=%s", type(e).__name__, str(e)[:300])
            if "rate" in str(e).lower() or "429" in str(e):
                raise ModelThrottledException(str(e)) from e
            raise
