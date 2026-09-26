"""
Token usage metric collector.
"""
from typing import List, Dict, Any
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from core.llm_factory import get_llm_factory


class TokenMetric:
    """Collect and analyze token usage."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.usage_records = []
        self.factory = get_llm_factory()

    def record(self, model: str, input_tokens: int, output_tokens: int):
        """Record token usage for a model."""
        total_tokens = input_tokens + output_tokens
        cost = self.factory.calculate_cost(model, input_tokens, output_tokens)

        self.usage_records.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
        })

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate token usage statistics."""
        if not self.usage_records:
            return {
                "error": "No token usage recorded",
                "passed": True,  # Not critical if no tokens used
            }

        # Aggregate by model
        by_model = {}
        total_input = 0
        total_output = 0
        total_tokens = 0
        total_cost = 0.0

        for record in self.usage_records:
            model = record["model"]
            if model not in by_model:
                by_model[model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "calls": 0,
                }

            by_model[model]["input_tokens"] += record["input_tokens"]
            by_model[model]["output_tokens"] += record["output_tokens"]
            by_model[model]["total_tokens"] += record["total_tokens"]
            by_model[model]["cost"] += record["cost"]
            by_model[model]["calls"] += 1

            total_input += record["input_tokens"]
            total_output += record["output_tokens"]
            total_tokens += record["total_tokens"]
            total_cost += record["cost"]

        # Check thresholds
        thresholds = self.config.get("thresholds", {})
        max_tokens = thresholds.get("max_tokens", 50000)
        max_cost = thresholds.get("max_cost_usd", 0.10)

        passed = total_tokens <= max_tokens and total_cost <= max_cost

        return {
            "eval_name": "token_usage",
            "passed": passed,
            "metrics": {
                "total_tokens": total_tokens,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_cost_usd": round(total_cost, 4),
                "avg_cost_per_call": round(total_cost / len(self.usage_records), 4),
                "num_calls": len(self.usage_records),
            },
            "by_model": by_model,
            "thresholds": {
                "max_tokens": max_tokens,
                "max_cost_usd": max_cost,
            },
            "violations": {
                "tokens_exceeded": total_tokens > max_tokens,
                "cost_exceeded": total_cost > max_cost,
            },
            "summary": f"Total: {total_tokens} tokens, ${total_cost:.4f} (max: {max_tokens} tokens, ${max_cost:.2f})",
        }
