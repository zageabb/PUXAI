from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any

from app.config import AppConfig
from app.services.ollama_client import OllamaClient


class AIBackend(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def generate_text(self, model: str, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        raise NotImplementedError


class OllamaBackend(AIBackend):
    def __init__(self, base_url: str, timeout_seconds: int = 180) -> None:
        self.client = OllamaClient(base_url, timeout_seconds=timeout_seconds)

    def is_available(self) -> bool:
        return self.client.is_available()

    def list_models(self) -> list[str]:
        return self.client.list_models()

    def generate_text(self, model: str, prompt: str, system: str | None = None) -> str:
        return self.client.generate_text(model=model, prompt=prompt, system=system)

    def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        payload, raw_response, error = self.client.generate_json(
            model=model,
            prompt=prompt,
            system=system,
        )
        return payload, raw_response, error


class DummyBackend(AIBackend):
    def is_available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["dummy-local"]

    def generate_text(self, model: str, prompt: str, system: str | None = None) -> str:
        lowered = prompt.lower()
        if "respond in concise markdown" in lowered:
            return (
                "Dummy backend response.\n\n"
                "- AI actions are running in test mode.\n"
                "- Switch `ai_backend` back to `ollama` for live model output."
            )
        return "Dummy backend response."

    def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        lowered = prompt.lower()
        payload: dict[str, Any]
        if "keys: reply, actions" in lowered:
            payload = {
                "reply": "Dummy backend is active. No live model actions were executed.",
                "actions": [],
            }
        elif "keys: status_suggestion, summary, next_step, checklist, labels" in lowered:
            payload = {
                "status_suggestion": "Backlog",
                "summary": "Dummy backend agent run completed in test mode.",
                "next_step": "Switch to the Ollama backend for live task agent output.",
                "checklist": ["Confirm backend selection", "Retry with Ollama if desired"],
                "labels": ["dummy"],
                "mermaid_artifacts": {},
                "notes": "No live model inference was performed.",
                "executor_action": "none",
            }
        else:
            payload = {
                "summary": "Dummy backend task draft.",
                "priority": "Medium",
                "labels": ["dummy"],
                "owner": "PUXAI",
                "checklist": ["Replace dummy backend with Ollama for richer output"],
                "agent_brief": "Dummy backend active.",
                "mermaid_artifacts": {},
                "repo_context_notes": "Generated without a live model.",
            }
        raw_response = json.dumps(payload)
        return payload, raw_response, None


class OpenAIBackend(AIBackend):
    # TODO: Implement OpenAI API support behind the shared backend interface.
    def is_available(self) -> bool:
        return False

    def list_models(self) -> list[str]:
        return []

    def generate_text(self, model: str, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError("OpenAI backend is not implemented yet.")

    def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        raise NotImplementedError("OpenAI backend is not implemented yet.")


class AzureOpenAIBackend(AIBackend):
    # TODO: Implement Azure OpenAI support behind the shared backend interface.
    def is_available(self) -> bool:
        return False

    def list_models(self) -> list[str]:
        return []

    def generate_text(self, model: str, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError("Azure OpenAI backend is not implemented yet.")

    def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        raise NotImplementedError("Azure OpenAI backend is not implemented yet.")


class CopilotBackend(AIBackend):
    # TODO: Implement Copilot-backed generation behind the shared backend interface.
    def is_available(self) -> bool:
        return False

    def list_models(self) -> list[str]:
        return []

    def generate_text(self, model: str, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError("Copilot backend is not implemented yet.")

    def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        raise NotImplementedError("Copilot backend is not implemented yet.")


def create_ai_backend(config: AppConfig) -> AIBackend | None:
    if not config.enable_ai:
        return None

    backend_name = str(config.ai_backend).strip().lower()
    if backend_name in {"", "ollama"}:
        return OllamaBackend(
            config.ollama_url,
            timeout_seconds=config.ollama_request_timeout_seconds,
        )
    if backend_name == "dummy":
        return DummyBackend()
    if backend_name == "openai":
        return DummyBackend()
    if backend_name == "azure_openai":
        return DummyBackend()
    if backend_name == "copilot":
        return DummyBackend()
    return OllamaBackend(
        config.ollama_url,
        timeout_seconds=config.ollama_request_timeout_seconds,
    )
