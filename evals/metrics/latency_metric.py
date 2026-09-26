"""
Latency metric collector.
"""
import numpy as np
from typing import List, Dict, Any


class LatencyMetric:
    """Collect and analyze latency metrics."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.latencies = []

    def record(self, latency_seconds: float):
        """Record a latency measurement."""
        self.latencies.append(latency_seconds)

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate latency statistics."""
        if not self.latencies:
            return {
                "error": "No latency measurements recorded",
                "passed": False,
            }

        latencies_array = np.array(self.latencies)

        p50 = float(np.percentile(latencies_array, 50))
        p95 = float(np.percentile(latencies_array, 95))
        p99 = float(np.percentile(latencies_array, 99))
        mean = float(np.mean(latencies_array))
        max_latency = float(np.max(latencies_array))
        min_latency = float(np.min(latencies_array))

        # Check thresholds
        thresholds = self.config.get("thresholds", {})
        p50_max = thresholds.get("p50_max", 5.0)
        p95_max = thresholds.get("p95_max", 10.0)

        passed = p50 <= p50_max and p95 <= p95_max

        return {
            "eval_name": "latency",
            "passed": passed,
            "metrics": {
                "p50": round(p50, 3),
                "p95": round(p95, 3),
                "p99": round(p99, 3),
                "mean": round(mean, 3),
                "max": round(max_latency, 3),
                "min": round(min_latency, 3),
                "count": len(self.latencies),
            },
            "thresholds": {
                "p50_max": p50_max,
                "p95_max": p95_max,
            },
            "violations": {
                "p50_exceeded": p50 > p50_max,
                "p95_exceeded": p95 > p95_max,
            },
            "summary": f"P50: {p50:.2f}s, P95: {p95:.2f}s (max P50: {p50_max}s, max P95: {p95_max}s)",
        }
