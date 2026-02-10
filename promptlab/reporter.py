"""Output formatting for analysis results.

Supports three output modes:
    - text     Rich terminal output with colors, tables, and progress bars
    - json     Machine-readable JSON
    - markdown Markdown-formatted report (good for pasting into docs)
"""

from __future__ import annotations

import json
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from promptlab.analyzer import AnalysisResult, DimensionScore
from promptlab.enhancer import EnhancementResult


def _score_color(score: float) -> str:
    """Return a Rich color name based on score value."""
    if score >= 8:
        return "green"
    if score >= 6:
        return "yellow"
    if score >= 4:
        return "dark_orange"
    return "red"


def _score_bar(score: float, width: int = 20) -> str:
    """Build a text-based progress bar for a score (1-10)."""
    filled = round((score / 10) * width)
    empty = width - filled
    return f"[{'=' * filled}{'-' * empty}]"


def _severity_color(severity_value: str) -> str:
    """Map severity level to a color."""
    return {"high": "red", "medium": "yellow", "low": "blue"}.get(severity_value, "white")


# ---------------------------------------------------------------------------
# Rich (text) output
# ---------------------------------------------------------------------------

def render_text(
    result: AnalysisResult,
    enhancement: Optional[EnhancementResult] = None,
    console: Optional[Console] = None,
) -> None:
    """Print a fully formatted analysis report to the terminal using Rich."""
    if console is None:
        console = Console()

    # Header
    console.print()
    console.print(
        Panel(
            Text("PromptLab Analysis Report", style="bold cyan", justify="center"),
            border_style="cyan",
        )
    )
    console.print()

    # Prompt preview (truncated if long)
    preview = result.prompt[:200]
    if len(result.prompt) > 200:
        preview += "..."
    console.print(Panel(preview, title="Prompt", border_style="dim"))
    console.print()

    # Quick stats
    console.print(f"  [dim]Words:[/] {result.word_count}    [dim]Sentences:[/] {result.sentence_count}")
    console.print()

    # Overall score
    color = _score_color(result.overall_score)
    console.print(f"  [bold]Overall Score:[/] [{color} bold]{result.overall_score}/10[/] ({result.overall_label})")
    console.print(f"  {_score_bar(result.overall_score, 30)}")
    console.print()

    # Dimension scores table
    table = Table(title="Dimension Scores", show_header=True, header_style="bold cyan")
    table.add_column("Dimension", style="bold", min_width=12)
    table.add_column("Score", justify="center", min_width=8)
    table.add_column("Rating", justify="center", min_width=10)
    table.add_column("Details", min_width=30)

    for dim in result.dimensions:
        color = _score_color(dim.score)
        bar = _score_bar(dim.score, 10)
        table.add_row(
            dim.name,
            f"[{color}]{dim.score}/10[/]",
            f"[{color}]{dim.label}[/]",
            dim.details,
        )

    console.print(table)
    console.print()

    # Anti-patterns
    if result.anti_patterns:
        console.print("[bold red]Anti-Patterns Detected[/]")
        console.print()
        for det in result.anti_patterns:
            sev_color = _severity_color(det.pattern.severity.value)
            console.print(
                f"  [{sev_color}][{det.pattern.severity.value.upper()}][/] "
                f"[bold]{det.pattern.name}[/]"
            )
            console.print(f"      {det.pattern.description}")
            if det.evidence:
                console.print(f"      [dim]Evidence: {det.evidence}[/]")
            console.print()

    # Suggestions
    if result.suggestions:
        console.print("[bold green]Suggestions for Improvement[/]")
        console.print()
        for i, suggestion in enumerate(result.suggestions, 1):
            console.print(f"  {i}. {suggestion}")
            console.print()

    # Enhancement (if present)
    if enhancement:
        console.print(
            Panel(
                enhancement.improved_prompt,
                title=f"AI-Enhanced Prompt ({enhancement.provider}/{enhancement.model})",
                border_style="magenta",
            )
        )
        console.print()
        if enhancement.explanation:
            console.print(f"  [dim]{enhancement.explanation}[/]")
            console.print()


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def render_json(
    result: AnalysisResult,
    enhancement: Optional[EnhancementResult] = None,
) -> str:
    """Return the analysis as a JSON string."""
    data = {
        "prompt": result.prompt,
        "overall_score": result.overall_score,
        "overall_label": result.overall_label,
        "word_count": result.word_count,
        "sentence_count": result.sentence_count,
        "dimensions": [
            {
                "name": d.name,
                "score": d.score,
                "max_score": d.max_score,
                "label": d.label,
                "details": d.details,
            }
            for d in result.dimensions
        ],
        "anti_patterns": [
            {
                "id": d.pattern.id,
                "name": d.pattern.name,
                "category": d.pattern.category.value,
                "severity": d.pattern.severity.value,
                "description": d.pattern.description,
                "suggestion": d.pattern.suggestion,
                "evidence": d.evidence,
            }
            for d in result.anti_patterns
        ],
        "suggestions": result.suggestions,
    }

    if enhancement:
        data["enhancement"] = {
            "improved_prompt": enhancement.improved_prompt,
            "explanation": enhancement.explanation,
            "provider": enhancement.provider,
            "model": enhancement.model,
        }

    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def render_markdown(
    result: AnalysisResult,
    enhancement: Optional[EnhancementResult] = None,
) -> str:
    """Return the analysis as a Markdown-formatted string."""
    lines: list[str] = []

    lines.append("# PromptLab Analysis Report")
    lines.append("")

    # Prompt
    lines.append("## Prompt")
    lines.append("")
    lines.append(f"> {result.prompt}")
    lines.append("")

    # Stats
    lines.append(f"**Words:** {result.word_count} | **Sentences:** {result.sentence_count}")
    lines.append("")

    # Overall
    lines.append(f"## Overall Score: {result.overall_score}/10 ({result.overall_label})")
    lines.append("")

    # Dimensions
    lines.append("## Dimension Scores")
    lines.append("")
    lines.append("| Dimension | Score | Rating | Details |")
    lines.append("|-----------|-------|--------|---------|")
    for dim in result.dimensions:
        lines.append(f"| {dim.name} | {dim.score}/10 | {dim.label} | {dim.details} |")
    lines.append("")

    # Anti-patterns
    if result.anti_patterns:
        lines.append("## Anti-Patterns Detected")
        lines.append("")
        for det in result.anti_patterns:
            lines.append(
                f"- **[{det.pattern.severity.value.upper()}] {det.pattern.name}**: "
                f"{det.pattern.description}"
            )
            if det.evidence:
                lines.append(f"  - *Evidence:* {det.evidence}")
        lines.append("")

    # Suggestions
    if result.suggestions:
        lines.append("## Suggestions")
        lines.append("")
        for i, suggestion in enumerate(result.suggestions, 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")

    # Enhancement
    if enhancement:
        lines.append("## AI-Enhanced Prompt")
        lines.append("")
        lines.append(f"*Provider: {enhancement.provider}/{enhancement.model}*")
        lines.append("")
        lines.append("```")
        lines.append(enhancement.improved_prompt)
        lines.append("```")
        lines.append("")
        if enhancement.explanation:
            lines.append(f"**Explanation:** {enhancement.explanation}")
            lines.append("")

    return "\n".join(lines)
