"""
Main evaluation runner with parallel LLM judge execution.
"""
import json
import time
import yaml
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel

from evals.judges import (
    DietarySafetyJudge,
    GroundTruthJudge,
    RelevanceJudge,
    LocationJudge,
)
from evals.metrics import LatencyMetric, TokenMetric
from core.llm_factory import get_llm_factory

console = Console()


class EvaluationRunner:
    """Orchestrate parallel evaluation with LLM judges."""

    def __init__(self, config_path: str = None, dataset_path: str = None):
        """Initialize runner with config and dataset."""
        # Load config
        if config_path is None:
            config_path = Path(__file__).parent / "eval_config.yaml"

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Load golden dataset
        if dataset_path is None:
            dataset_path = Path(__file__).parent / "golden_dataset.json"

        with open(dataset_path) as f:
            self.dataset = json.load(f)

        # Initialize LLM factory
        self.llm_factory = get_llm_factory()

        # Initialize judges and metrics
        self.judges = self._initialize_judges()
        self.latency_metric = LatencyMetric(
            self.config["evaluations"].get("latency", {})
        )
        self.token_metric = TokenMetric(
            self.config["evaluations"].get("token_usage", {})
        )

        # Results storage
        self.results = {
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "dataset": self.dataset["dataset_name"],
                "dataset_version": self.dataset["version"],
                "config_version": "1.0",
            },
            "test_results": [],
            "summary": {},
        }

    def _initialize_judges(self) -> Dict[str, Any]:
        """Initialize all enabled judges."""
        judges = {}
        eval_configs = self.config["evaluations"]

        # Map eval names to judge classes
        judge_map = {
            "dietary_safety": DietarySafetyJudge,
            "ground_truth": GroundTruthJudge,
            "relevance": RelevanceJudge,
            "geo_location": LocationJudge,
        }

        for eval_name, judge_class in judge_map.items():
            eval_config = eval_configs.get(eval_name, {})

            if eval_config.get("enabled", True):
                # Add name and judge prompts to config
                eval_config["name"] = eval_name

                # Get judge prompt if available
                judge_prompts = self.config.get("judge_prompts", {})
                if eval_name in judge_prompts:
                    eval_config["prompt_template"] = judge_prompts[eval_name]

                judges[eval_name] = judge_class(eval_config, self.llm_factory)

        return judges

    def run_agent_on_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the meal helper agent on a test case.

        NOTE: This is a placeholder. In production, you'd import and run your actual agent.
        For now, we'll simulate agent responses for demonstration.
        """
        # TODO: Replace with actual agent execution
        # from core.agent import MealHelperAgent
        # agent = MealHelperAgent(user_profile=UserProfile(**test_case["user_profile"]))
        # result = agent.chat(test_case["query"])

        # SIMULATION: Generate mock result for testing the eval framework
        return self._simulate_agent_result(test_case)

    def _simulate_agent_result(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate agent result for testing (remove in production)."""
        # Return mock recommendations based on test case
        user_profile = test_case.get("user_profile", {})
        budget = user_profile.get("budget", {}).get("max_per_meal", 20)

        return {
            "success": True,
            "recommendations": [
                {
                    "name": "Margherita Pizza",
                    "restaurant": "Joe's Pizza",
                    "price": "$12.99",
                    "description": "Classic tomato and mozzarella",
                    "location": user_profile.get("location", {}),
                },
                {
                    "name": "Pepperoni Pizza",
                    "restaurant": "Pizza Suprema",
                    "price": "$14.50",
                    "description": "Pepperoni with extra cheese",
                    "location": user_profile.get("location", {}),
                },
            ],
            "metadata": {
                "model": "gpt-5.4-mini",
                "tokens": {"input": 500, "output": 300, "total": 800},
            },
        }

    def evaluate_single_test(
        self, test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate a single test case with all judges."""
        test_id = test_case.get("id", "unknown")
        test_name = test_case.get("name", "Unknown Test")

        console.print(f"\n[cyan]Running test:[/cyan] {test_name} ({test_id})")

        # Run agent and measure latency
        start_time = time.time()
        agent_result = self.run_agent_on_test(test_case)
        latency = time.time() - start_time

        # Record latency
        self.latency_metric.record(latency)

        # Record tokens if available
        metadata = agent_result.get("metadata", {})
        tokens = metadata.get("tokens", {})
        if tokens:
            model = metadata.get("model", "unknown")
            self.token_metric.record(
                model,
                tokens.get("input", 0),
                tokens.get("output", 0),
            )

        # Run all judges in parallel
        judge_results = self._run_judges_parallel(test_case, agent_result)

        # Compile test result
        test_result = {
            "test_id": test_id,
            "test_name": test_name,
            "query": test_case.get("query"),
            "latency_seconds": round(latency, 3),
            "agent_result": agent_result,
            "judge_results": judge_results,
            "passed": all(r.passed for r in judge_results.values()),
            "critical_failure": self._check_critical_failure(judge_results),
        }

        return test_result

    def _run_judges_parallel(
        self, test_case: Dict[str, Any], agent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run all judges in parallel using ThreadPoolExecutor."""
        max_workers = self.config.get("execution", {}).get("max_concurrent_llm_calls", 5)

        judge_results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all judge tasks
            future_to_judge = {
                executor.submit(judge.evaluate, test_case, agent_result): name
                for name, judge in self.judges.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_judge):
                judge_name = future_to_judge[future]
                try:
                    result = future.result()
                    judge_results[judge_name] = result

                    # Record tokens from judge
                    if result.tokens_used:
                        self.token_metric.record(
                            result.model_used,
                            result.tokens_used.get("input", 0),
                            result.tokens_used.get("output", 0),
                        )

                    # Display result
                    status = "✅ PASS" if result.passed else "❌ FAIL"
                    console.print(
                        f"  [{judge_name}] Score: {result.score:.1f}/5.0 - {status}"
                    )

                except Exception as e:
                    console.print(f"  [{judge_name}] ❌ ERROR: {str(e)}", style="red")
                    judge_results[judge_name] = {
                        "error": str(e),
                        "passed": False,
                    }

        return judge_results

    def _check_critical_failure(self, judge_results: Dict[str, Any]) -> bool:
        """Check if any critical evaluation failed."""
        critical_evals = ["dietary_safety", "geo_location", "ground_truth"]

        for eval_name in critical_evals:
            if eval_name in judge_results:
                result = judge_results[eval_name]
                if not result.passed:
                    eval_config = self.config["evaluations"].get(eval_name, {})
                    if eval_config.get("thresholds", {}).get("critical", False):
                        return True

        return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run evaluation on all test cases."""
        console.print("\n[bold cyan]🧪 Starting Meal Helper Evaluation Suite[/bold cyan]\n")

        test_cases = self.dataset.get("test_cases", [])
        total_tests = len(test_cases)

        console.print(f"[yellow]Total test cases:[/yellow] {total_tests}")
        console.print(f"[yellow]Enabled judges:[/yellow] {', '.join(self.judges.keys())}\n")

        # Run each test
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Running evaluations...", total=total_tests)

            for test_case in test_cases:
                try:
                    test_result = self.evaluate_single_test(test_case)
                    self.results["test_results"].append(test_result)
                except Exception as e:
                    console.print(f"\n[red]ERROR in test {test_case.get('id')}:[/red] {str(e)}")
                    self.results["test_results"].append({
                        "test_id": test_case.get("id"),
                        "error": str(e),
                        "passed": False,
                    })
                finally:
                    progress.advance(task)

        # Calculate metrics
        self._calculate_summary()

        return self.results

    def _calculate_summary(self):
        """Calculate summary statistics."""
        test_results = self.results["test_results"]
        total_tests = len(test_results)
        passed_tests = sum(1 for t in test_results if t.get("passed", False))
        failed_tests = total_tests - passed_tests
        critical_failures = sum(1 for t in test_results if t.get("critical_failure", False))

        # Aggregate judge scores
        judge_scores = {}
        for judge_name in self.judges.keys():
            scores = []
            for test in test_results:
                judge_result = test.get("judge_results", {}).get(judge_name)
                if judge_result and hasattr(judge_result, "score"):
                    scores.append(judge_result.score)

            if scores:
                # Get min_score threshold if available (default to 3)
                eval_config = self.config["evaluations"].get(judge_name, {})
                thresholds = eval_config.get("thresholds", {})
                min_score_threshold = thresholds.get("min_score", 3)

                judge_scores[judge_name] = {
                    "mean_score": round(sum(scores) / len(scores), 2),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "passed_count": sum(1 for s in scores if s >= min_score_threshold),
                    "total_count": len(scores),
                    "threshold": min_score_threshold,
                }

        self.results["summary"] = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "pass_rate": round((passed_tests / total_tests) * 100, 2) if total_tests > 0 else 0,
            "critical_failures": critical_failures,
            "judge_scores": judge_scores,
            "latency_metrics": self.latency_metric.calculate_metrics(),
            "token_metrics": self.token_metric.calculate_metrics(),
        }

    def display_summary(self):
        """Display evaluation summary in console."""
        summary = self.results["summary"]

        console.print("\n" + "=" * 80)
        console.print("[bold cyan]📊 EVALUATION SUMMARY[/bold cyan]")
        console.print("=" * 80 + "\n")

        # Overall results
        table = Table(title="Overall Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Total Tests", str(summary["total_tests"]))
        table.add_row("Passed", f"[green]{summary['passed']}[/green]")
        table.add_row("Failed", f"[red]{summary['failed']}[/red]")
        table.add_row("Pass Rate", f"{summary['pass_rate']}%")
        table.add_row("Critical Failures", f"[red bold]{summary['critical_failures']}[/red bold]")

        console.print(table)

        # Judge scores
        console.print("\n[bold]Judge Performance:[/bold]\n")
        judge_table = Table()
        judge_table.add_column("Judge", style="cyan")
        judge_table.add_column("Mean Score", style="yellow")
        judge_table.add_column("Range", style="magenta")
        judge_table.add_column("Pass Rate", style="green")

        for judge_name, scores in summary["judge_scores"].items():
            pass_rate = (scores["passed_count"] / scores["total_count"]) * 100
            judge_table.add_row(
                judge_name,
                f"{scores['mean_score']:.2f}/5.0",
                f"{scores['min_score']:.1f} - {scores['max_score']:.1f}",
                f"{pass_rate:.1f}%",
            )

        console.print(judge_table)

        # Latency metrics
        latency = summary["latency_metrics"]
        console.print(f"\n[bold]Latency:[/bold] {latency.get('summary', 'N/A')}")

        # Token metrics
        tokens = summary["token_metrics"]
        console.print(f"[bold]Tokens:[/bold] {tokens.get('summary', 'N/A')}")

        # Final verdict
        if summary["critical_failures"] > 0:
            console.print("\n[bold red]⚠️  CRITICAL FAILURES DETECTED[/bold red]")
        elif summary["pass_rate"] >= 90:
            console.print("\n[bold green]✅ EVALUATION PASSED[/bold green]")
        elif summary["pass_rate"] >= 70:
            console.print("\n[bold yellow]⚠️  EVALUATION NEEDS IMPROVEMENT[/bold yellow]")
        else:
            console.print("\n[bold red]❌ EVALUATION FAILED[/bold red]")

    def save_results(self, output_path: str = None):
        """Save results to JSON file."""
        if output_path is None:
            results_dir = Path(__file__).parent / "results"
            results_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = results_dir / f"eval_results_{timestamp}.json"

        # Convert JudgeResult objects to dicts for JSON serialization
        serializable_results = self._make_serializable(self.results)

        with open(output_path, "w") as f:
            json.dump(serializable_results, f, indent=2)

        console.print(f"\n[green]Results saved to:[/green] {output_path}")
        return str(output_path)

    def _make_serializable(self, obj):
        """Convert objects to JSON-serializable format."""
        # Pydantic V2 uses model_dump() instead of dict()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "dict"):
            return obj.dict()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj


def main():
    """Main entry point."""
    runner = EvaluationRunner()

    try:
        results = runner.run_all_tests()
        runner.display_summary()
        output_file = runner.save_results()

        return results

    except KeyboardInterrupt:
        console.print("\n[yellow]Evaluation interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]ERROR:[/red] {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
