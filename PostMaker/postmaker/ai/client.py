"""AI 客户端（LiteLLM 封装）"""

from __future__ import annotations

from typing import Any, Dict, List

import litellm
from litellm import completion

litellm.suppress_debug_info = True


class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.model = config.get("model", "")
        self.api_key = config.get("api_key", "")
        self.api_base = config.get("api_base", "")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 8000)
        self.timeout = config.get("timeout", 120)
        self.models = config.get("models", {})

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        params: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "timeout": kwargs.get("timeout", self.timeout),
            "num_retries": 2,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base

        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens and max_tokens > 0:
            params["max_tokens"] = max_tokens

        response = completion(**params)
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return content or ""

    def get_model_for_importance(self, importance: float) -> str:
        if importance >= 4 and self.models.get("high"):
            return self.models["high"]
        if self.models.get("medium"):
            return self.models["medium"]
        return self.model

    def validate(self) -> tuple[bool, str]:
        if not self.model:
            return False, "未配置 AI 模型"
        if not self.api_key:
            return False, "未配置 API Key"
        return True, ""
