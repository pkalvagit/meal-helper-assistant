"""
Base judge class for LLM-based evaluation.
"""
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.llm_factory import get_llm_factory


class JudgeResult(BaseModel):
    """Result from a judge evaluation."""
    eval_name: str
    score: float  # 1-5
    passed: bool
    reasoning: str
    details: Dict[str, Any] = {}
    latency_ms: float = 0.0
    tokens_used: Optional[Dict[str, int]] = None
    model_used: str = ""
    timestamp: float = 0.0


class BaseJudge(ABC):
    """Base class for all LLM judges."""

    def __init__(self, config: Dict[str, Any], llm_factory=None):
        """
        Initialize judge with configuration.

        Args:
            config: Eval configuration from eval_config.yaml
            llm_factory: Optional LLM factory (will create if not provided)
        """
        self.config = config
        self.eval_name = config.get("name", self.__class__.__name__)
        self.llm_required = config.get("llm_required", True)
        self.factory = llm_factory or get_llm_factory()

        # Get LLM if required
        self.llm = None
        self.model_name = None
        if self.llm_required:
            provider = config.get("provider", "openai")
            model = config.get("llm_model", "gpt-5.4-mini")

            # Create temporary config in the factory format
            llm_config = {
                "provider": provider,
                provider: {
                    "model": model,
                    "max_tokens": config.get("max_tokens", 1000),
                    "temperature": config.get("temperature", 0.1),
                }
            }

            # Get LLM instance
            if provider == "claude":
                self.llm = self.factory._create_claude(llm_config[provider])
            else:
                self.llm = self.factory._create_openai(llm_config[provider])

            self.model_name = model

    @abstractmethod
    def build_prompt(self, test_case: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Build the evaluation prompt for this judge."""
        pass

    @abstractmethod
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured data."""
        pass

    @abstractmethod
    def calculate_score(self, parsed_response: Dict[str, Any]) -> float:
        """Calculate final score (1-5) from parsed response."""
        pass

    def evaluate(
        self,
        test_case: Dict[str, Any],
        agent_result: Dict[str, Any]
    ) -> JudgeResult:
        """
        Run evaluation on test case and agent result.

        Args:
            test_case: Test case from golden dataset
            agent_result: Result from running agent on test case

        Returns:
            JudgeResult with score and details
        """
        start_time = time.time()

        # Build prompt
        prompt = self.build_prompt(test_case, agent_result)

        # Call LLM if required
        if self.llm_required and self.llm:
            response = self.llm.invoke(prompt)
            response_text = response.content

            # Track tokens if available
            tokens_used = None
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("token_usage", {})
                if usage:
                    tokens_used = {
                        "input": usage.get("prompt_tokens", 0),
                        "output": usage.get("completion_tokens", 0),
                        "total": usage.get("total_tokens", 0),
                    }

            # Parse response
            parsed = self.parse_response(response_text)
        else:
            # No LLM needed - programmatic evaluation
            parsed = self.evaluate_programmatic(test_case, agent_result)
            response_text = json.dumps(parsed)
            tokens_used = None

        # Calculate score
        score = self.calculate_score(parsed)

        # Check if passed
        min_score = self.config.get("thresholds", {}).get("min_score", 3)
        passed = score >= min_score

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        return JudgeResult(
            eval_name=self.eval_name,
            score=score,
            passed=passed,
            reasoning=parsed.get("reasoning", ""),
            details=parsed,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            model_used=self.model_name or "programmatic",
            timestamp=time.time(),
        )

    def evaluate_programmatic(
        self,
        test_case: Dict[str, Any],
        agent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Programmatic evaluation (for non-LLM judges).
        Override in subclass if llm_required=False.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} requires LLM but evaluate_programmatic not implemented"
        )

    def extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback: return error
        return {
            "error": "Could not parse JSON from response",
            "raw_response": text,
            "score": 0,
            "reasoning": "Failed to parse LLM response"
        }
