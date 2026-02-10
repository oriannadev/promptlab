"""Optional AI-powered prompt enhancement.

When the user provides an API key (via PROMPTLAB_API_KEY env var), this
module calls an LLM to generate an improved version of the original prompt,
informed by the local analysis results.

Supported providers (set via PROMPTLAB_PROVIDER env var):
    - openai   (default) -- OpenAI ChatCompletion API
    - anthropic          -- Anthropic Messages API
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from promptlab.analyzer import AnalysisResult


@dataclass
class EnhancementResult:
    """Result from the AI enhancement step."""

    improved_prompt: str
    explanation: str
    provider: str
    model: str


class EnhancerError(Exception):
    """Raised when enhancement fails (missing key, API error, etc.)."""


def _build_system_message(result: AnalysisResult) -> str:
    """Build the system prompt that gives the LLM context about the analysis."""
    anti_pattern_list = "\n".join(
        f"  - {d.pattern.name}: {d.evidence}" for d in result.anti_patterns
    )
    suggestion_list = "\n".join(f"  - {s}" for s in result.suggestions)

    return (
        "You are an expert prompt engineer. The user has a prompt that was "
        "analyzed by an automated tool. Your job is to rewrite the prompt to "
        "address the identified issues while preserving the user's original intent.\n\n"
        f"Overall score: {result.overall_score}/10\n\n"
        f"Detected issues:\n{anti_pattern_list or '  (none)'}\n\n"
        f"Suggestions:\n{suggestion_list or '  (none)'}\n\n"
        "Return ONLY:\n"
        "1. The improved prompt (clearly labeled)\n"
        "2. A brief explanation of what you changed and why (2-4 sentences)\n\n"
        "Do not add commentary beyond these two sections."
    )


def _enhance_openai(prompt: str, result: AnalysisResult, api_key: str) -> EnhancementResult:
    """Call OpenAI's ChatCompletion API."""
    try:
        import openai
    except ImportError:
        raise EnhancerError(
            "The 'openai' package is required for OpenAI enhancement. "
            "Install it with: pip install openai"
        )

    client = openai.OpenAI(api_key=api_key)
    model = os.getenv("PROMPTLAB_MODEL", "gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _build_system_message(result)},
                {"role": "user", "content": f"Here is the prompt to improve:\n\n{prompt}"},
            ],
            temperature=0.7,
            max_tokens=1500,
        )
        content = response.choices[0].message.content or ""
    except Exception as e:
        raise EnhancerError(f"OpenAI API error: {e}")

    improved, explanation = _parse_enhancement_response(content)
    return EnhancementResult(
        improved_prompt=improved,
        explanation=explanation,
        provider="openai",
        model=model,
    )


def _enhance_anthropic(prompt: str, result: AnalysisResult, api_key: str) -> EnhancementResult:
    """Call Anthropic's Messages API."""
    try:
        import anthropic
    except ImportError:
        raise EnhancerError(
            "The 'anthropic' package is required for Anthropic enhancement. "
            "Install it with: pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key)
    model = os.getenv("PROMPTLAB_MODEL", "claude-sonnet-4-20250514")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=_build_system_message(result),
            messages=[
                {"role": "user", "content": f"Here is the prompt to improve:\n\n{prompt}"},
            ],
        )
        content = response.content[0].text
    except Exception as e:
        raise EnhancerError(f"Anthropic API error: {e}")

    improved, explanation = _parse_enhancement_response(content)
    return EnhancementResult(
        improved_prompt=improved,
        explanation=explanation,
        provider="anthropic",
        model=model,
    )


def _parse_enhancement_response(content: str) -> tuple[str, str]:
    """Split the LLM response into the improved prompt and explanation.

    We look for common section markers. If we can't find a clean split,
    we treat the whole response as the improved prompt.
    """
    import re

    # Try to find labeled sections
    improved_match = re.search(
        r'(?:improved prompt|rewritten prompt|enhanced prompt)[:\s]*\n(.*?)(?=\n(?:explanation|what i changed|changes made)|$)',
        content,
        re.I | re.S,
    )
    explanation_match = re.search(
        r'(?:explanation|what i changed|changes made)[:\s]*\n(.*)',
        content,
        re.I | re.S,
    )

    if improved_match and explanation_match:
        return improved_match.group(1).strip(), explanation_match.group(1).strip()

    # Fallback: split on double newline -- first block is prompt, rest is explanation
    parts = content.strip().split("\n\n", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()

    return content.strip(), "See improved prompt above."


def enhance(prompt: str, result: AnalysisResult) -> EnhancementResult:
    """Enhance a prompt using an AI provider.

    Reads configuration from environment variables:
        PROMPTLAB_API_KEY  -- required
        PROMPTLAB_PROVIDER -- "openai" (default) or "anthropic"
        PROMPTLAB_MODEL    -- override the default model

    Args:
        prompt: The original prompt text.
        result: The local analysis result (used to inform the LLM).

    Returns:
        An EnhancementResult with the improved prompt and explanation.

    Raises:
        EnhancerError: If no API key is set or the API call fails.
    """
    api_key = os.getenv("PROMPTLAB_API_KEY", "").strip()
    if not api_key:
        raise EnhancerError(
            "No API key found. Set the PROMPTLAB_API_KEY environment variable.\n"
            "  export PROMPTLAB_API_KEY=sk-your-key-here"
        )

    provider = os.getenv("PROMPTLAB_PROVIDER", "openai").lower().strip()

    if provider == "openai":
        return _enhance_openai(prompt, result, api_key)
    elif provider == "anthropic":
        return _enhance_anthropic(prompt, result, api_key)
    else:
        raise EnhancerError(
            f"Unknown provider '{provider}'. Supported: openai, anthropic"
        )
