#!/usr/bin/env python3
"""
CLI for Meal Helper Assistant.
"""
import json
import os
import warnings
from pathlib import Path
from typing import Optional

# Suppress deprecation warnings for cleaner output
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load .env file FIRST (before any other imports)
from dotenv import load_dotenv
load_dotenv()

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Use simple agent (compatible with all LangChain versions)
from core.simple_agent import SimpleMealHelperAgent as MealHelperAgent
from core.models import UserProfile
from core.logger import setup_logger, log_chat_start, log_user_message, log_agent_response
from core.stats_logger import StatsLogger

app = typer.Typer(help="🍽️ Meal Helper Assistant - Find restaurants matching your dietary needs")
console = Console()


def load_user_profile(profile_name: str) -> Optional[UserProfile]:
    """Load user profile from config."""
    config_path = Path(__file__).parent / "config" / "user_profiles.json"

    if not config_path.exists():
        console.print("[red]No user profiles found[/red]")
        return None

    with open(config_path) as f:
        profiles = json.load(f)

    if profile_name not in profiles:
        console.print(f"[red]Profile '{profile_name}' not found[/red]")
        console.print(f"Available profiles: {', '.join(profiles.keys())}")
        return None

    return UserProfile(**profiles[profile_name])


@app.command()
def chat(
    profile: str = typer.Option(
        "example_user",
        "--profile",
        "-p",
        help="User profile name from config/user_profiles.json"
    ),
    query: Optional[str] = typer.Option(
        None,
        "--query",
        "-q",
        help="Single query (non-interactive mode)"
    )
):
    """
    Start interactive chat session or run single query.

    Examples:
        # Interactive mode
        python run.py chat --profile example_user

        # Single query
        python run.py chat -q "Find high protein lunch under $15"
    """
    # Setup loggers
    logger = setup_logger()
    stats_logger = StatsLogger()
    log_chat_start(logger, profile)

    # Load user profile
    user_profile = load_user_profile(profile)
    if not user_profile:
        raise typer.Exit(1)

    # Show profile
    console.print(Panel(
        f"[bold]User:[/bold] {user_profile.name}\n"
        f"[bold]Allergies:[/bold] {', '.join(user_profile.allergies) or 'None'}\n"
        f"[bold]Restrictions:[/bold] {', '.join(user_profile.dietary_restrictions) or 'None'}\n"
        f"[bold]Budget:[/bold] ${user_profile.budget.max_per_meal}/meal",
        title="🍽️ Meal Helper Assistant",
        border_style="green"
    ))

    # Create agent (logging goes to files)
    console.print("[dim]Initializing agent...[/dim]", end="")
    agent = MealHelperAgent(user_profile, logger=logger, stats_logger=stats_logger)
    console.print(" [green]✓[/green]")

    # Single query mode
    if query:
        log_user_message(logger, query)
        console.print(f"\n[bold blue]You:[/bold blue] {query}")
        response = agent.chat(query)

        log_agent_response(logger, response.message)
        console.print(f"\n[bold green]Assistant:[/bold green]")
        console.print(Markdown(response.message))
        console.print(f"\n[dim]Cost: ${response.cost:.4f}[/dim]")

        # Print stats summary
        stats_logger.print_stats_summary()
        return

    # Interactive mode
    console.print("\n[dim]Type your questions or 'quit' to exit[/dim]\n")

    total_cost = 0.0

    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ")

            if user_input.lower() in ["quit", "exit", "q"]:
                console.print(f"\n[bold]Total cost:[/bold] ${total_cost:.4f}")
                stats_logger.print_stats_summary()
                break

            if user_input.lower() == "reset":
                agent.reset_conversation()
                logger.info("Conversation reset by user")
                console.print("[yellow]Conversation reset[/yellow]\n")
                continue

            # Log and get response
            log_user_message(logger, user_input)

            # Show progress header
            console.print("\n[cyan]━━━ Processing your request ━━━[/cyan]\n")

            response = agent.chat(user_input)

            log_agent_response(logger, response.message)
            console.print(f"\n[cyan]━━━ Results ━━━[/cyan]\n")
            console.print(Markdown(response.message))

            total_cost += response.cost
            console.print(f"\n[dim]💰 Cost: ${response.cost:.4f} | Session Total: ${total_cost:.4f}[/dim]\n")

        except KeyboardInterrupt:
            console.print(f"\n\n[bold]Total cost:[/bold] ${total_cost:.4f}")
            stats_logger.print_stats_summary()
            break


@app.command()
def list_profiles():
    """List available user profiles."""
    config_path = Path(__file__).parent / "config" / "user_profiles.json"

    with open(config_path) as f:
        profiles = json.load(f)

    console.print("\n[bold]Available Profiles:[/bold]\n")

    for name, data in profiles.items():
        console.print(Panel(
            f"[bold]Name:[/bold] {data.get('name', 'N/A')}\n"
            f"[bold]Allergies:[/bold] {', '.join(data.get('allergies', [])) or 'None'}\n"
            f"[bold]Restrictions:[/bold] {', '.join(data.get('dietary_restrictions', [])) or 'None'}\n"
            f"[bold]Budget:[/bold] ${data.get('budget', {}).get('max_per_meal', 20.0)}/meal",
            title=f"Profile: {name}",
            border_style="cyan"
        ))


@app.command()
def test_guardrails(
    query: str = typer.Argument(..., help="Query to test")
):
    """
    Test guardrail on a query.

    Example:
        python run.py test-guardrails "Tell me a joke"
    """
    from core.guardrails import RestaurantGuardrail

    guardrail = RestaurantGuardrail()
    result = guardrail.check_query(query)

    console.print(Panel(
        f"[bold]Query:[/bold] {query}\n\n"
        f"[bold]Valid:[/bold] {'✅' if result.is_valid else '❌'}\n"
        f"[bold]Reason:[/bold] {result.reason or 'N/A'}\n"
        f"[bold]Intent:[/bold] {result.intent.dict() if result.intent else 'N/A'}\n"
        f"[bold]Cost:[/bold] ${result.cost:.6f}",
        title="Guardrail Test",
        border_style="yellow"
    ))


@app.command()
def run_evals():
    """Run evaluation suite."""
    from evals.run_evals import run_all_evals

    console.print("[bold]Running evaluation suite...[/bold]\n")
    results = run_all_evals()

    console.print(Panel(
        f"[bold]Total Tests:[/bold] {results['total']}\n"
        f"[bold]Passed:[/bold] {results['passed']}\n"
        f"[bold]Failed:[/bold] {results['failed']}\n"
        f"[bold]Pass Rate:[/bold] {results['pass_rate']:.1f}%",
        title="Eval Results",
        border_style="green" if results['pass_rate'] >= 80 else "red"
    ))


if __name__ == "__main__":
    app()
