"""Click CLI entry point for PromptLab.

Provides the `promptlab analyze` command with options for input source,
output format, and optional AI enhancement.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console

from promptlab import __version__
from promptlab.analyzer import analyze
from promptlab.enhancer import EnhancerError, enhance
from promptlab.reporter import render_json, render_markdown, render_text

console = Console()


def _read_prompt(prompt_text: str | None, file: str | None) -> str:
    """Resolve the prompt from the argument, a file, or stdin."""
    if prompt_text:
        return prompt_text

    if file:
        try:
            with open(file, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            console.print(f"[red]Error:[/] File not found: {file}")
            raise SystemExit(1)
        except OSError as e:
            console.print(f"[red]Error:[/] Could not read file: {e}")
            raise SystemExit(1)

    # Try reading from stdin (piped input)
    if not sys.stdin.isatty():
        return sys.stdin.read()

    console.print("[red]Error:[/] No prompt provided.")
    console.print("Pass a prompt as an argument, use --file, or pipe via stdin.")
    console.print()
    console.print("  promptlab analyze \"Your prompt here\"")
    console.print("  promptlab analyze --file prompt.txt")
    console.print("  echo \"Your prompt\" | promptlab analyze")
    raise SystemExit(1)


@click.group()
@click.version_option(version=__version__, prog_name="promptlab")
def cli() -> None:
    """PromptLab -- Analyze and improve your prompts."""


@cli.command()
@click.argument("prompt_text", required=False, default=None)
@click.option("--file", "-f", type=str, help="Read prompt from a file.")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON.")
@click.option("--markdown", "output_md", is_flag=True, help="Output results as Markdown.")
@click.option(
    "--enhance",
    "enhance_flag",
    is_flag=True,
    help="Use an AI provider to generate an improved prompt (requires PROMPTLAB_API_KEY).",
)
def analyze_cmd(
    prompt_text: str | None,
    file: str | None,
    output_json: bool,
    output_md: bool,
    enhance_flag: bool = False,
) -> None:
    """Analyze a prompt for quality and get improvement suggestions.

    Pass the prompt as a quoted argument, point to a file with --file,
    or pipe text via stdin.

    \b
    Examples:
        promptlab analyze "Write me something about dogs"
        promptlab analyze --file my_prompt.txt
        promptlab analyze "Write a blog post" --json
        echo "Fix my code" | promptlab analyze --markdown
    """
    prompt = _read_prompt(prompt_text, file)

    if not prompt.strip():
        console.print("[red]Error:[/] Prompt is empty.")
        raise SystemExit(1)

    # Run the core analysis
    result = analyze(prompt)

    # Optionally enhance with AI
    enhancement = None
    if enhance_flag:
        try:
            enhancement = enhance(prompt, result)
        except EnhancerError as e:
            console.print(f"[yellow]Enhancement skipped:[/] {e}")
            console.print()

    # Render the output
    if output_json:
        click.echo(render_json(result, enhancement))
    elif output_md:
        click.echo(render_markdown(result, enhancement))
    else:
        render_text(result, enhancement, console=console)


# Alias so `promptlab analyze` is the main command but the group
# still works for future sub-commands (e.g., `promptlab batch`).
cli.add_command(analyze_cmd, name="analyze")


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
