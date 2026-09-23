"""
LLM Factory - Configurable support for Claude and OpenAI.
"""
import os
import ssl
import yaml
from pathlib import Path
from typing import Literal, Optional

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

# Disable SSL verification globally if requested (for corporate proxies)
if os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
    import warnings
    import logging
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    # This will affect urllib3/requests used by OpenAI SDK
    ssl._create_default_https_context = ssl._create_unverified_context
    logging.getLogger("meal-helper").info("SSL verification disabled (corporate proxy mode)")


class LLMFactory:
    """Factory for creating LLM instances based on configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "llm_config.yaml"

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

    def get_llm(
        self,
        llm_type: Literal["primary", "guardrail"] = "primary",
        provider: Optional[str] = None
    ) -> BaseChatModel:
        """
        Get LLM instance based on config.

        Args:
            llm_type: "primary" or "guardrail"
            provider: Override provider from config ("claude" or "openai")

        Returns:
            LangChain chat model instance
        """
        llm_config = self.config[llm_type]
        provider = provider or llm_config["provider"]

        if provider == "claude":
            return self._create_claude(llm_config["claude"])
        elif provider == "openai":
            return self._create_openai(llm_config["openai"])
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _create_claude(self, config: dict) -> ChatAnthropic:
        """Create Claude instance."""
        kwargs = {
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "temperature": config.get("temperature", 0.7),
        }

        # Add thinking config if present
        if "thinking" in config:
            kwargs["thinking"] = config["thinking"]

        # Add API key if set
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            kwargs["anthropic_api_key"] = api_key

        return ChatAnthropic(**kwargs)

    def _create_openai(self, config: dict) -> ChatOpenAI:
        """Create OpenAI instance."""
        kwargs = {
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "temperature": config.get("temperature", 0.7),
        }

        # Add API key if set
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            kwargs["openai_api_key"] = api_key

        # Disable SSL verification if requested (for corporate proxies)
        if os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
            import httpx
            http_client = httpx.Client(verify=False)
            kwargs["http_client"] = http_client

        return ChatOpenAI(**kwargs)

    def get_model_cost(self, model: str) -> tuple[float, float]:
        """Get (input_cost, output_cost) per 1M tokens."""
        costs = self.config["cost_per_1m_tokens"]
        if model in costs:
            return costs[model]["input"], costs[model]["output"]
        return 0.0, 0.0

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD."""
        input_cost, output_cost = self.get_model_cost(model)
        return (input_tokens * input_cost / 1_000_000 +
                output_tokens * output_cost / 1_000_000)


# Singleton instance
_factory = None

def get_llm_factory() -> LLMFactory:
    """Get singleton LLM factory."""
    global _factory
    if _factory is None:
        _factory = LLMFactory()
    return _factory
