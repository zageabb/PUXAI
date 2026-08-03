"""Small Responses API client with optional hosted web search."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

import requests


@dataclass(frozen=True)
class AIResponse:
    """Normalized model result for the desktop UI."""

    text: str
    response_id: str | None = None
    sources: list[dict[str, str]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


class OpenAIBackend:
    """Call OpenAI's Responses API without requiring an SDK dependency."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, api_key_env_var: str, model: str, timeout_seconds: int = 60) -> None:
        self.api_key_env_var = api_key_env_var
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(os.environ.get(self.api_key_env_var, "").strip())

    def respond(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        web_search: bool = False,
        instructions: str | None = None,
    ) -> AIResponse:
        api_key = os.environ.get(self.api_key_env_var, "").strip()
        if not api_key:
            raise RuntimeError(
                f"Set the {self.api_key_env_var} environment variable before using AI chat."
            )

        payload: dict[str, Any] = {
            "model": model or self.model,
            "input": [{"role": item["role"], "content": item["content"]} for item in messages],
            "instructions": instructions or (
                "You are PUX AI, a practical personal operations and research assistant. "
                "Answer clearly, preserve useful detail, distinguish facts from assumptions, "
                "and cite sources when web research is used."
            ),
            "store": False,
        }
        if web_search:
            payload["tools"] = [{"type": "web_search"}]
            payload["include"] = ["web_search_call.action.sources"]

        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not reach the AI service: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"AI service returned an invalid response ({response.status_code}).") from exc
        if not response.ok:
            detail = data.get("error", {}).get("message") or data.get("message") or response.reason
            raise RuntimeError(f"AI request failed: {detail}")

        text_parts: list[str] = []
        sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text_parts.append(part.get("text", ""))
                        for annotation in part.get("annotations", []):
                            if annotation.get("type") == "url_citation":
                                url = annotation.get("url", "")
                                if url and url not in seen_urls:
                                    seen_urls.add(url)
                                    sources.append({"title": annotation.get("title") or url, "url": url})
            if item.get("type") == "web_search_call":
                for source in item.get("action", {}).get("sources", []) or []:
                    url = source.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        sources.append({"title": source.get("title") or url, "url": url})

        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            raise RuntimeError("The AI service completed without returning text.")
        usage = data.get("usage") or {}
        return AIResponse(
            text=text,
            response_id=data.get("id"),
            sources=sources,
            usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
        )
