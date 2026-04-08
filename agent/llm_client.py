from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests
from dotenv import load_dotenv


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CURRENT_DIR, ".env"))


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "groq")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

        if not self.api_key:
            raise ValueError("LLM_API_KEY is missing in agent/.env")

    def chat_json(self, *, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        request_body = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Return only one valid JSON object and no prose.\n"
                        + json.dumps(user_payload, ensure_ascii=True)
                    ),
                },
            ],
        }

        last_error: Exception | None = None
        for delay in (0, 2, 5):
            if delay:
                time.sleep(delay)
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=120,
            )
            if response.ok:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return self._parse_json_content(content)
            last_error = requests.HTTPError(
                f"{response.status_code} error from {self.provider} API: {response.text}",
                response=response,
            )
            if response.status_code != 429:
                break

        raise last_error if last_error else RuntimeError("Unknown LLM API error")

    def chat_text(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
        request_body = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        last_error: Exception | None = None
        for delay in (0, 2, 5):
            if delay:
                time.sleep(delay)
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=120,
            )
            if response.ok:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content.strip()
            last_error = requests.HTTPError(
                f"{response.status_code} error from {self.provider} API: {response.text}",
                response=response,
            )
            if response.status_code != 429:
                break

        raise last_error if last_error else RuntimeError("Unknown LLM API error")

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise
