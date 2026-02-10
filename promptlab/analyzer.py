"""Core prompt analysis engine.

Scores a prompt across multiple quality dimensions using rule-based
heuristics, regex pattern matching, and keyword detection. No API key
or external service is required -- everything runs locally.

Dimensions scored (1-10 each):
    - Clarity:     Is the prompt specific and unambiguous?
    - Structure:   Does it include role, context, task, and output format?
    - Specificity: Are there constraints, examples, and edge-case handling?
    - Length:      Is the prompt appropriately sized (not too short, not bloated)?

The overall score is a weighted average of the four dimensions.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from promptlab.patterns import (
    ALL_PATTERNS,
    CONSTRAINT_KEYWORDS,
    CONTEXT_SIGNALS,
    EXAMPLE_KEYWORDS,
    OUTPUT_FORMAT_KEYWORDS,
    ROLE_KEYWORDS,
    AntiPattern,
    Category,
)


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """Score for a single analysis dimension."""

    name: str
    score: float  # 1.0 - 10.0
    max_score: float = 10.0
    details: str = ""

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score) * 100

    @property
    def label(self) -> str:
        if self.score >= 8:
            return "Excellent"
        if self.score >= 6:
            return "Good"
        if self.score >= 4:
            return "Fair"
        if self.score >= 2:
            return "Weak"
        return "Poor"


@dataclass
class DetectedAntiPattern:
    """An anti-pattern that was found in the prompt."""

    pattern: AntiPattern
    evidence: str = ""  # the matched text that triggered detection


@dataclass
class AnalysisResult:
    """Complete analysis of a single prompt."""

    prompt: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    anti_patterns: list[DetectedAntiPattern] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    word_count: int = 0
    sentence_count: int = 0

    @property
    def overall_score(self) -> float:
        """Weighted average across all dimensions."""
        if not self.dimensions:
            return 0.0

        weights = {
            "Clarity": 0.30,
            "Structure": 0.25,
            "Specificity": 0.25,
            "Length": 0.20,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for dim in self.dimensions:
            w = weights.get(dim.name, 0.25)
            weighted_sum += dim.score * w
            total_weight += w

        return round(weighted_sum / total_weight, 1) if total_weight else 0.0

    @property
    def overall_label(self) -> str:
        s = self.overall_score
        if s >= 8:
            return "Excellent"
        if s >= 6:
            return "Good"
        if s >= 4:
            return "Fair"
        if s >= 2:
            return "Weak"
        return "Poor"


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    return len(text.split())


def _count_sentences(text: str) -> int:
    # Split on sentence-ending punctuation followed by whitespace or end
    parts = re.split(r'[.!?]+(?:\s|$)', text.strip())
    return max(1, len([p for p in parts if p.strip()]))


def _has_any_keyword(text_lower: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text_lower for kw in keywords)


def _count_keyword_hits(text_lower: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for kw in keywords if kw in text_lower)


def _count_distinct_tasks(text: str) -> int:
    """Estimate how many separate tasks are being requested.

    Heuristic: count imperative verbs that start clauses (allowing for
    optional transition words like 'also', 'and', 'can you'), question
    marks, and explicit task-separator phrases.
    """
    verb_pattern = (
        r'(write|create|generate|build|make|list|explain|describe|summarize|'
        r'translate|convert|fix|improve|update|edit|rewrite|help|tell|give|'
        r'design|develop|analyze|compare|review)'
    )
    # Match verbs at sentence starts, allowing transition words before the verb
    task_starters = re.findall(
        r'(?:^|[.!?]\s+|\n\s*)'
        r'(?:(?:and\s+)?(?:also\s+|can\s+you\s+(?:also\s+)?)?)?'
        + verb_pattern + r'\b',
        text,
        re.I,
    )
    questions = text.count("?")
    return len(task_starters) + questions


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _score_clarity(text: str, text_lower: str) -> DimensionScore:
    """Score how clear and unambiguous the prompt is.

    Factors: absence of vague language, sentence complexity, use of
    concrete nouns vs. abstract hand-waving.
    """
    score = 7.0  # start optimistic, deduct for problems
    details_parts: list[str] = []

    # Penalize vague language
    from promptlab.patterns import VAGUE_LANGUAGE

    vague_hits = 0
    for pattern in VAGUE_LANGUAGE.positive_signals:
        if pattern.search(text):
            vague_hits += 1
    for kw in VAGUE_LANGUAGE.keyword_signals:
        if kw in text_lower:
            vague_hits += 1

    if vague_hits >= 3:
        score -= 4.0
        details_parts.append("Multiple vague phrases detected")
    elif vague_hits >= 1:
        score -= 2.0 * vague_hits
        details_parts.append(f"{vague_hits} vague phrase(s) detected")

    # Penalize very short prompts (< 5 words) -- too ambiguous
    word_count = _count_words(text)
    if word_count < 5:
        score -= 3.0
        details_parts.append("Extremely short -- likely too ambiguous")
    elif word_count < 10:
        score -= 1.5
        details_parts.append("Very short -- may lack clarity")

    # Reward specificity signals (numbers, proper nouns, technical terms)
    numbers = len(re.findall(r'\b\d+\b', text))
    if numbers >= 2:
        score += 1.0
        details_parts.append("Contains numeric specifics")

    # Penalize ambiguous pronoun starts
    from promptlab.patterns import AMBIGUOUS_PRONOUNS

    for pattern in AMBIGUOUS_PRONOUNS.positive_signals:
        if pattern.search(text):
            score -= 1.5
            details_parts.append("Starts with an ambiguous pronoun reference")
            break

    score = max(1.0, min(10.0, score))
    return DimensionScore(
        name="Clarity",
        score=round(score, 1),
        details="; ".join(details_parts) if details_parts else "Clear and specific",
    )


def _score_structure(text: str, text_lower: str) -> DimensionScore:
    """Score whether the prompt has the key structural components.

    Components: role/persona, context, task definition, output format.
    Each present component adds ~2.5 points to a base of 0.
    """
    score = 0.0
    present: list[str] = []
    missing: list[str] = []

    # Role / persona
    if _has_any_keyword(text_lower, ROLE_KEYWORDS):
        score += 2.5
        present.append("role")
    else:
        missing.append("role/persona")

    # Context
    if _has_any_keyword(text_lower, CONTEXT_SIGNALS):
        score += 2.5
        present.append("context")
    else:
        missing.append("context/background")

    # Clear task (has at least one imperative verb)
    task_verbs = re.findall(
        r'\b(write|create|generate|build|make|list|explain|describe|summarize|'
        r'translate|convert|fix|improve|update|edit|rewrite|analyze|compare|'
        r'design|develop|review|draft|compose|produce|outline|calculate)\b',
        text_lower,
    )
    if task_verbs:
        score += 2.5
        present.append("task")
    else:
        missing.append("clear task verb")

    # Output format
    if _has_any_keyword(text_lower, OUTPUT_FORMAT_KEYWORDS):
        score += 2.5
        present.append("output format")
    else:
        missing.append("output format")

    score = max(1.0, min(10.0, score))
    detail_str = ""
    if present:
        detail_str += f"Has: {', '.join(present)}"
    if missing:
        detail_str += f". Missing: {', '.join(missing)}"
    return DimensionScore(name="Structure", score=round(score, 1), details=detail_str.strip(". "))


def _score_specificity(text: str, text_lower: str) -> DimensionScore:
    """Score how specific and constrained the prompt is.

    Factors: constraints/boundaries, examples, quantitative details,
    edge-case mentions.
    """
    score = 2.0  # low base -- specificity must be earned
    details_parts: list[str] = []

    # Constraints
    constraint_hits = _count_keyword_hits(text_lower, CONSTRAINT_KEYWORDS)
    if constraint_hits >= 5:
        score += 3.0
        details_parts.append("Strong constraints present")
    elif constraint_hits >= 2:
        score += 2.0
        details_parts.append("Some constraints present")
    elif constraint_hits >= 1:
        score += 1.0
        details_parts.append("Minimal constraints")
    else:
        details_parts.append("No constraints detected")

    # Examples
    if _has_any_keyword(text_lower, EXAMPLE_KEYWORDS):
        score += 2.5
        details_parts.append("Includes examples")
    else:
        details_parts.append("No examples provided")

    # Quantitative specifics
    numbers = len(re.findall(r'\b\d+\b', text))
    if numbers >= 3:
        score += 1.5
        details_parts.append("Multiple numeric details")
    elif numbers >= 1:
        score += 0.75

    # Multi-line / structured input (shows effort)
    lines = [l for l in text.strip().split("\n") if l.strip()]
    if len(lines) >= 5:
        score += 1.0
        details_parts.append("Well-structured multi-line prompt")

    score = max(1.0, min(10.0, score))
    return DimensionScore(
        name="Specificity",
        score=round(score, 1),
        details="; ".join(details_parts),
    )


def _score_length(text: str) -> DimensionScore:
    """Score prompt length -- penalize extremes, reward the sweet spot.

    Sweet spot heuristic: 20-300 words for most tasks.
    Very short (<10 words) or very long (>500 words) are penalized.
    """
    word_count = _count_words(text)

    if word_count < 5:
        score = 2.0
        detail = f"{word_count} words -- too short to convey a meaningful task"
    elif word_count < 10:
        score = 4.0
        detail = f"{word_count} words -- quite short, likely missing details"
    elif word_count < 20:
        score = 6.0
        detail = f"{word_count} words -- on the short side"
    elif word_count <= 300:
        # Sweet spot -- scale from 8 to 10
        score = 8.0 + min(2.0, (word_count - 20) / 140)
        detail = f"{word_count} words -- good length"
    elif word_count <= 500:
        score = 7.0
        detail = f"{word_count} words -- on the long side, consider trimming"
    else:
        # Gradually penalize extreme length
        overshoot = word_count - 500
        score = max(3.0, 7.0 - (overshoot / 200))
        detail = f"{word_count} words -- quite long, risk of losing focus"

    return DimensionScore(
        name="Length",
        score=round(min(10.0, score), 1),
        details=detail,
    )


# ---------------------------------------------------------------------------
# Anti-pattern detection
# ---------------------------------------------------------------------------

def _detect_anti_patterns(text: str, text_lower: str) -> list[DetectedAntiPattern]:
    """Run all defined anti-pattern checks against the prompt."""
    detected: list[DetectedAntiPattern] = []

    for ap in ALL_PATTERNS:
        found = False
        evidence = ""

        # -- Patterns detected by ABSENCE of keywords --
        if ap.id == "missing_role":
            if not _has_any_keyword(text_lower, ROLE_KEYWORDS):
                found = True
                evidence = "No role or persona assignment found"

        elif ap.id == "missing_output_format":
            if not _has_any_keyword(text_lower, OUTPUT_FORMAT_KEYWORDS):
                found = True
                evidence = "No output format specification found"

        elif ap.id == "missing_context":
            if not _has_any_keyword(text_lower, CONTEXT_SIGNALS):
                found = True
                evidence = "No contextual background found"

        elif ap.id == "no_constraints":
            if _count_keyword_hits(text_lower, CONSTRAINT_KEYWORDS) == 0:
                found = True
                evidence = "No constraint or boundary keywords found"

        elif ap.id == "no_examples":
            if not _has_any_keyword(text_lower, EXAMPLE_KEYWORDS):
                found = True
                evidence = "No example or sample output found"

        # -- Patterns detected by PRESENCE of signals --
        elif ap.id == "multiple_requests":
            distinct = _count_distinct_tasks(text)
            if distinct >= 3:
                found = True
                evidence = f"Detected ~{distinct} distinct tasks/requests"

        else:
            # Generic: check regex and keyword signals
            for pattern in ap.positive_signals:
                match = pattern.search(text)
                if match:
                    found = True
                    evidence = f'Matched: "{match.group()}"'
                    break

            if not found:
                for kw in ap.keyword_signals:
                    if kw in text_lower:
                        found = True
                        evidence = f'Contains: "{kw}"'
                        break

        if found:
            detected.append(DetectedAntiPattern(pattern=ap, evidence=evidence))

    return detected


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------

def _generate_suggestions(
    dimensions: list[DimensionScore],
    anti_patterns: list[DetectedAntiPattern],
) -> list[str]:
    """Build a prioritized list of actionable suggestions."""
    suggestions: list[str] = []
    seen_ids: set[str] = set()

    # Suggestions from anti-patterns (highest severity first)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    sorted_patterns = sorted(
        anti_patterns,
        key=lambda d: severity_order.get(d.pattern.severity.value, 3),
    )
    for det in sorted_patterns:
        if det.pattern.id not in seen_ids:
            suggestions.append(det.pattern.suggestion)
            seen_ids.add(det.pattern.id)

    # If all dimensions scored well but there's room for improvement
    low_dims = [d for d in dimensions if d.score < 6.0]
    if not low_dims and not suggestions:
        suggestions.append(
            "This is already a strong prompt. Consider adding edge-case "
            "handling or examples for even better results."
        )

    return suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(prompt: str) -> AnalysisResult:
    """Analyze a prompt and return a complete scored result.

    Args:
        prompt: The raw prompt text to analyze.

    Returns:
        An AnalysisResult with scores, detected anti-patterns, and suggestions.
    """
    text = prompt.strip()
    if not text:
        return AnalysisResult(
            prompt=prompt,
            dimensions=[
                DimensionScore(name="Clarity", score=1.0, details="Empty prompt"),
                DimensionScore(name="Structure", score=1.0, details="Empty prompt"),
                DimensionScore(name="Specificity", score=1.0, details="Empty prompt"),
                DimensionScore(name="Length", score=1.0, details="0 words"),
            ],
            suggestions=["Provide a non-empty prompt to analyze."],
            word_count=0,
            sentence_count=0,
        )

    text_lower = text.lower()

    dimensions = [
        _score_clarity(text, text_lower),
        _score_structure(text, text_lower),
        _score_specificity(text, text_lower),
        _score_length(text),
    ]

    anti_patterns = _detect_anti_patterns(text, text_lower)
    suggestions = _generate_suggestions(dimensions, anti_patterns)

    return AnalysisResult(
        prompt=text,
        dimensions=dimensions,
        anti_patterns=anti_patterns,
        suggestions=suggestions,
        word_count=_count_words(text),
        sentence_count=_count_sentences(text),
    )
