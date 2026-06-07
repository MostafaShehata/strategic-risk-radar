import json
import re
from typing import Any

import httpx


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        enabled: bool = True,
        timeout_seconds: int = 90,
        num_predict: int = 350,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.num_predict = num_predict

    def json_task(self, system: str, user: str) -> dict[str, Any]:
        if not self.enabled:
            return {}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_name,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "options": {"temperature": 0.1, "num_predict": self.num_predict},
                    },
                )
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
                return self.extract_json(content)
        except Exception:
            return {}

    def extract_json(self, content: str) -> dict[str, Any]:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        candidate = fenced.group(1) if fenced else content
        if not candidate.startswith("{"):
            match = re.search(r"\{.*\}", candidate, re.DOTALL)
            candidate = match.group(0) if match else "{}"
        return json.loads(candidate)
