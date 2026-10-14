"""Thin client for any OpenAI-compatible endpoint (OpenAI, Groq, Ollama's /v1, vLLM, ...).

Disabled unless LLM_BASE_URL and LLM_MODEL are set; callers must handle `None` and fall back.
"""

import json
import logging
import math
import os

import httpx

log = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 embedding_model: str | None = None, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "LLMClient | None":
        base_url, model = os.getenv("LLM_BASE_URL"), os.getenv("LLM_MODEL")
        if not base_url or not model:
            return None
        return cls(base_url, model, os.getenv("LLM_API_KEY"), os.getenv("EMBEDDING_MODEL"))

    def complete_json(self, system: str, user: str) -> dict | None:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            resp = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            log.warning("LLM completion failed: %s", exc)
            return None

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not self.embedding_model:
            return None
        try:
            resp = httpx.post(f"{self.base_url}/embeddings", json={"model": self.embedding_model, "input": texts},
                              headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]
        except (httpx.HTTPError, KeyError) as exc:
            log.warning("Embedding request failed: %s", exc)
            return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
