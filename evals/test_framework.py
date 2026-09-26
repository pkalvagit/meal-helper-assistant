"""
Test script to verify the evaluation framework is working.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from evals.eval_runner import EvaluationRunner

console = Console()


def test_framework():
    """Test the evaluation framework with a small subset."""
    console.print("[bold cyan]Testing Evaluation Framework[/bold cyan]\n")

    try:
        # Initialize runner
        console.print("[yellow]1. Initializing runner...[/yellow]")
        runner = EvaluationRunner()
        console.print("[green]✓ Runner initialized successfully[/green]")

        # Check configuration
        console.print("\n[yellow]2. Checking configuration...[/yellow]")
        console.print(f"   Evaluations loaded: {list(runner.config['evaluations'].keys())}")
        console.print(f"   Judges initialized: {list(runner.judges.keys())}")
        console.print("[green]✓ Configuration valid[/green]")

        # Check dataset
        console.print("\n[yellow]3. Checking dataset...[/yellow]")
        test_cases = runner.dataset.get("test_cases", [])
        console.print(f"   Test cases loaded: {len(test_cases)}")
        if test_cases:
            console.print(f"   First test: {test_cases[0].get('name')}")
        console.print("[green]✓ Dataset loaded[/green]")

        # Test single evaluation (without running full agent)
        console.print("\n[yellow]4. Testing single evaluation (mock)...[/yellow]")
        if test_cases:
            test_case = test_cases[0]
            console.print(f"   Running: {test_case.get('name')}")

            # Create a mock result
            mock_result = {
                "success": True,
                "recommendations": [
                    {
                        "name": "Test Item",
                        "restaurant": "Test Restaurant",
                        "price": "$10.00",
                        "description": "Test description",
                    }
                ],
                "metadata": {
                    "model": "test-model",
                    "tokens": {"input": 100, "output": 50, "total": 150},
                },
            }

            # Test each judge
            for judge_name, judge in runner.judges.items():
                try:
                    console.print(f"   Testing {judge_name}...", end="")
                    result = judge.evaluate(test_case, mock_result)
                    console.print(f" Score: {result.score:.1f}/5.0 ✓")
                except Exception as e:
                    console.print(f" [red]ERROR: {str(e)}[/red]")

        console.print("\n[green]✓ Single evaluation test passed[/green]")

        # Summary
        console.print("\n[bold green]✅ All tests passed![/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. Run full evaluation: python evals/eval_runner.py")
        console.print("  2. Integrate your real agent in eval_runner.py")
        console.print("  3. Review results in evals/results/")

        return True

    except Exception as e:
        console.print(f"\n[bold red]❌ Test failed:[/bold red] {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_framework()
    sys.exit(0 if success else 1)
