from __future__ import annotations

import json

from app.services.ollama_client import OllamaClient, _extract_json_candidate


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_extract_json_candidate_strips_code_fences() -> None:
    raw = "```json\n{\"ok\": true}\n```"

    result = _extract_json_candidate(raw)

    assert result == '{"ok": true}'


def test_generate_json_uses_extracted_candidate_without_network(monkeypatch) -> None:
    def fake_post(url: str, json: dict, timeout: int) -> FakeResponse:  # noqa: A002
        return FakeResponse({"response": "```json\n{\"reply\": \"ok\"}\n```"})

    monkeypatch.setattr("app.services.ollama_client.requests.post", fake_post)
    client = OllamaClient("http://localhost:11434")

    payload, raw, error = client.generate_json("demo", "prompt")

    assert payload == {"reply": "ok"}
    assert raw.startswith("```json")
    assert error is None
