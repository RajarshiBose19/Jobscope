from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from google import genai
from google.genai import types as gtypes
from jobscope import config

class RateLimitError(Exception):
    pass

class AnalysisFailure(Exception):
    pass

@dataclass
class GeminiResult:
    text: str

class GeminiClient:
    def __init__(self, keys: list[str], model: str):
        if not keys:
            raise ValueError("GeminiClient requires at least one API key")
        self._keys = keys
        self._idx = 0
        self._current_key = keys[0]
        self._model = model
        self._client = genai.Client(api_key=self._current_key)

    def _rotate(self) -> bool:
        self._idx += 1
        if self._idx >= len(self._keys):
            return False
        self._current_key = self._keys[self._idx]
        self._client = genai.Client(api_key=self._current_key)
        return True

    def _call_once(self, system: str, user: str, response_schema) -> GeminiResult:
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=user,
                config=gtypes.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=config.GEMINI_TEMPERATURE,
                ),
            )
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "quota" in msg or "rate" in msg:
                raise RateLimitError(str(e)) from e
            raise
        return GeminiResult(text=resp.text)

    def generate_json(self, *, system: str, user: str, response_schema: Any) -> GeminiResult:
        attempts = 0
        while True:
            attempts += 1
            try:
                return self._call_once(system, user, response_schema)
            except RateLimitError:
                if not self._rotate():
                    raise AnalysisFailure(
                        f"All Gemini API keys exhausted after {attempts} attempts"
                    )
