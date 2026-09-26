"""
Evaluation suite for Meal Helper Assistant.
"""
import json
from pathlib import Path
from typing import Dict, Any, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.guardrails import RestaurantGuardrail
from core.models import UserProfile
from tools.filter_tool import filter_menu_by_user_profile

console = Console()


def load_test_cases() -> Dict[str, List[Dict[str, Any]]]:
    """Load test cases from JSON."""
    test_file = Path(__file__).parent / "test_cases.json"
    with open(test_file) as f:
        return json.load(f)


def eval_guardrails() -> Dict[str, Any]:
    """Evaluate guardrail accuracy."""
    console.print("\n[bold cyan]Running Guardrail Tests...[/bold cyan]")

    test_cases = load_test_cases()["guardrail_tests"]
    guardrail = RestaurantGuardrail()

    passed = 0
    failed = 0
    results = []

    table = Table(title="Guardrail Eval Results")
    table.add_column("Query", style="cyan", width=40)
    table.add_column("Expected", style="yellow", width=10)
    table.add_column("Actual", style="yellow", width=10)
    table.add_column("Result", style="green", width=10)

    for test in test_cases:
        query = test["query"]
        expected = test["expected_valid"]

        result = guardrail.check_query(query)
        actual = result.is_valid

        is_pass = expected == actual
        if is_pass:
            passed += 1
        else:
            failed += 1

        table.add_row(
            query[:40],
            "✅" if expected else "❌",
            "✅" if actual else "❌",
            "✅ PASS" if is_pass else "❌ FAIL"
        )

        results.append({
            "query": query,
            "expected": expected,
            "actual": actual,
            "pass": is_pass
        })

    console.print(table)

    return {
        "category": "guardrails",
        "passed": passed,
        "failed": failed,
        "total": len(test_cases),
        "pass_rate": (passed / len(test_cases)) * 100,
        "results": results
    }


def eval_safety() -> Dict[str, Any]:
    """Evaluate allergen safety (CRITICAL - must be 100%)."""
    console.print("\n[bold red]Running Safety Tests (Allergen Filtering)...[/bold red]")

    test_cases = load_test_cases()["safety_tests"]

    passed = 0
    failed = 0
    results = []

    for test in test_cases:
        profile = UserProfile(**test["user_profile"])
        menu_items = test["menu_items"]
        expected_safe = set(test["expected_safe_items"])
        expected_filtered = set(test["expected_filtered"])

        # Run filter
        filter_result = filter_menu_by_user_profile.invoke({
            "menu_items": menu_items,
            "allergies": profile.allergies,
            "dietary_restrictions": profile.dietary_restrictions,
            "max_price": profile.budget.max_per_meal,
        })

        # Check results
        safe_items = {item["name"] for item in filter_result["filtered_items"]}
        removed_items = set(filter_result["removal_reasons"].keys())

        # CRITICAL: No allergens should pass through
        allergen_leak = safe_items & expected_filtered
        is_safe = len(allergen_leak) == 0

        # Check if correct items were kept
        correct_safe = expected_safe == safe_items

        is_pass = is_safe and correct_safe

        if is_pass:
            passed += 1
        else:
            failed += 1

        console.print(Panel(
            f"[bold]Test:[/bold] {test['description']}\n"
            f"[bold]Allergens:[/bold] {', '.join(profile.allergies)}\n"
            f"[bold]Restrictions:[/bold] {', '.join(profile.dietary_restrictions)}\n\n"
            f"[bold]Expected Safe:[/bold] {', '.join(expected_safe)}\n"
            f"[bold]Actual Safe:[/bold] {', '.join(safe_items)}\n"
            f"[bold]Filtered:[/bold] {', '.join(removed_items)}\n\n"
            f"[bold]Allergen Leak:[/bold] {', '.join(allergen_leak) if allergen_leak else 'None ✅'}\n"
            f"[bold]Result:[/bold] {'✅ PASS' if is_pass else '❌ FAIL'}",
            border_style="green" if is_pass else "red"
        ))

        results.append({
            "description": test["description"],
            "safe": is_safe,
            "correct": correct_safe,
            "pass": is_pass,
            "allergen_leak": list(allergen_leak)
        })

    return {
        "category": "safety",
        "passed": passed,
        "failed": failed,
        "total": len(test_cases),
        "pass_rate": (passed / len(test_cases)) * 100,
        "results": results,
        "critical": True  # Safety tests are critical
    }


def eval_intent_extraction() -> Dict[str, Any]:
    """Evaluate intent extraction accuracy."""
    console.print("\n[bold cyan]Running Intent Extraction Tests...[/bold cyan]")

    test_cases = load_test_cases()["intent_extraction_tests"]
    guardrail = RestaurantGuardrail()

    passed = 0
    failed = 0
    results = []

    for test in test_cases:
        query = test["query"]
        expected = test["expected"]

        result = guardrail.check_query(query)
        if not result.intent:
            failed += 1
            continue

        intent = result.intent

        # Check each expected field
        matches = []
        for key, value in expected.items():
            actual_value = getattr(intent, key, None)
            matches.append(actual_value == value)

        is_pass = all(matches)
        if is_pass:
            passed += 1
        else:
            failed += 1

        console.print(f"Query: {query}")
        console.print(f"  Expected: {expected}")
        console.print(f"  Actual: {intent.dict()}")
        console.print(f"  Result: {'✅ PASS' if is_pass else '❌ FAIL'}\n")

        results.append({
            "query": query,
            "expected": expected,
            "actual": intent.dict(),
            "pass": is_pass
        })

    return {
        "category": "intent_extraction",
        "passed": passed,
        "failed": failed,
        "total": len(test_cases),
        "pass_rate": (passed / len(test_cases)) * 100,
        "results": results
    }


def run_all_evals() -> Dict[str, Any]:
    """Run all evaluation tests."""
    console.print("[bold]🧪 Meal Helper Assistant - Evaluation Suite[/bold]\n")

    results = {
        "guardrails": eval_guardrails(),
        "safety": eval_safety(),
        "intent_extraction": eval_intent_extraction(),
    }

    # Summary
    total_passed = sum(r["passed"] for r in results.values())
    total_failed = sum(r["failed"] for r in results.values())
    total_tests = sum(r["total"] for r in results.values())
    overall_pass_rate = (total_passed / total_tests) * 100

    # Check critical tests
    critical_pass = results["safety"]["pass_rate"] == 100

    console.print("\n" + "=" * 70)
    console.print("[bold]SUMMARY[/bold]")
    console.print("=" * 70)

    summary_table = Table()
    summary_table.add_column("Category", style="cyan")
    summary_table.add_column("Passed", style="green")
    summary_table.add_column("Failed", style="red")
    summary_table.add_column("Total", style="yellow")
    summary_table.add_column("Pass Rate", style="magenta")

    for category, data in results.items():
        is_critical = data.get("critical", False)
        category_name = f"{category.upper()} {'(CRITICAL)' if is_critical else ''}"

        summary_table.add_row(
            category_name,
            str(data["passed"]),
            str(data["failed"]),
            str(data["total"]),
            f"{data['pass_rate']:.1f}%"
        )

    summary_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_passed}[/bold]",
        f"[bold]{total_failed}[/bold]",
        f"[bold]{total_tests}[/bold]",
        f"[bold]{overall_pass_rate:.1f}%[/bold]"
    )

    console.print(summary_table)

    if not critical_pass:
        console.print("\n[bold red]⚠️  CRITICAL FAILURE: Safety tests did not pass 100%[/bold red]")
    elif overall_pass_rate >= 90:
        console.print("\n[bold green]✅ All tests passed![/bold green]")
    elif overall_pass_rate >= 70:
        console.print("\n[bold yellow]⚠️  Some tests failed[/bold yellow]")
    else:
        console.print("\n[bold red]❌ Many tests failed[/bold red]")

    return {
        "total": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "pass_rate": overall_pass_rate,
        "critical_pass": critical_pass,
        "details": results
    }


if __name__ == "__main__":
    run_all_evals()
