"""Anti-pattern definitions and detection rules for prompt analysis.

Each pattern is a dataclass containing:
- A unique identifier and human-readable name
- The detection logic (regex patterns and/or keyword checks)
- The severity and suggestion for fixing it

The patterns are grouped by category so the analyzer can report
findings in a structured way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """How much a detected anti-pattern hurts prompt quality."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Category(Enum):
    """Broad grouping for anti-patterns."""

    STRUCTURE = "structure"
    CLARITY = "clarity"
    SPECIFICITY = "specificity"
    SCOPE = "scope"


@dataclass(frozen=True)
class AntiPattern:
    """A single detectable anti-pattern in a prompt."""

    id: str
    name: str
    category: Category
    severity: Severity
    description: str
    suggestion: str
    # Compiled regex patterns that signal this anti-pattern
    positive_signals: tuple[re.Pattern[str], ...] = field(default_factory=tuple)
    # Keywords / phrases (lowercase) that signal this anti-pattern
    keyword_signals: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Structure patterns
# ---------------------------------------------------------------------------

MISSING_ROLE = AntiPattern(
    id="missing_role",
    name="Missing Role / Persona",
    category=Category.STRUCTURE,
    severity=Severity.MEDIUM,
    description="The prompt does not assign a role or persona to the AI.",
    suggestion=(
        "Start with a role assignment like 'You are an experienced technical "
        "writer...' to ground the AI's perspective and expertise level."
    ),
    positive_signals=(),  # detected by *absence* of role keywords
)

MISSING_OUTPUT_FORMAT = AntiPattern(
    id="missing_output_format",
    name="No Output Format Specified",
    category=Category.STRUCTURE,
    severity=Severity.MEDIUM,
    description="The prompt does not specify what format the output should take.",
    suggestion=(
        "Specify the desired output format, e.g. 'Return the result as a "
        "numbered list', 'Format as JSON', or 'Write a 3-paragraph essay'."
    ),
)

MISSING_CONTEXT = AntiPattern(
    id="missing_context",
    name="Missing Context / Background",
    category=Category.STRUCTURE,
    severity=Severity.HIGH,
    description="The prompt lacks background information or context for the task.",
    suggestion=(
        "Add context about the audience, purpose, or background situation. "
        "For example: 'I'm writing a blog for beginner Python developers...'"
    ),
)

# ---------------------------------------------------------------------------
# Clarity patterns
# ---------------------------------------------------------------------------

VAGUE_LANGUAGE = AntiPattern(
    id="vague_language",
    name="Vague / Hand-wavy Language",
    category=Category.CLARITY,
    severity=Severity.HIGH,
    description="The prompt uses vague qualifiers instead of concrete instructions.",
    suggestion=(
        "Replace vague words with specific criteria. Instead of 'make it good', "
        "say 'ensure the tone is professional and each paragraph has a topic sentence'."
    ),
    positive_signals=(
        re.compile(r"\bmake\s+it\s+(good|better|nice|great|awesome|perfect)\b", re.I),
        re.compile(r"\bimprove\s+this\b", re.I),
        re.compile(r"\bdo\s+(something|a\s+good\s+job|your\s+best)\b", re.I),
        re.compile(r"\bsomething\s+(about|on|related)\b", re.I),
        re.compile(r"\bwhatever\s+you\s+think\b", re.I),
        re.compile(r"\bjust\s+make\s+it\s+work\b", re.I),
    ),
    keyword_signals=(
        "make it good",
        "make it better",
        "make it nice",
        "do something",
        "whatever you think",
        "you decide",
        "be creative",
        "do your best",
        "just make it work",
    ),
)

AMBIGUOUS_PRONOUNS = AntiPattern(
    id="ambiguous_pronouns",
    name="Ambiguous Pronoun References",
    category=Category.CLARITY,
    severity=Severity.LOW,
    description=(
        "The prompt uses pronouns ('it', 'this', 'that') without clear referents, "
        "which can confuse the model."
    ),
    suggestion=(
        "Replace ambiguous pronouns with explicit nouns. Instead of "
        "'Improve it and make it shorter', say 'Improve the product description "
        "and reduce it to under 50 words'."
    ),
    positive_signals=(
        # Starts with a pronoun reference to something not in the prompt
        re.compile(r"^(fix|improve|change|update|rewrite|edit|modify)\s+(it|this|that)\b", re.I),
    ),
)

# ---------------------------------------------------------------------------
# Specificity patterns
# ---------------------------------------------------------------------------

NO_CONSTRAINTS = AntiPattern(
    id="no_constraints",
    name="No Constraints or Boundaries",
    category=Category.SPECIFICITY,
    severity=Severity.MEDIUM,
    description="The prompt sets no limits on length, scope, tone, or format.",
    suggestion=(
        "Add constraints like word count, tone, audience level, or scope. "
        "Example: 'Keep it under 200 words, written for a non-technical audience.'"
    ),
)

NO_EXAMPLES = AntiPattern(
    id="no_examples",
    name="No Examples Provided",
    category=Category.SPECIFICITY,
    severity=Severity.LOW,
    description=(
        "The prompt does not include examples of desired input/output, "
        "which helps the model understand expectations."
    ),
    suggestion=(
        "Add 1-2 examples of what good output looks like. Few-shot examples "
        "dramatically improve output quality for structured tasks."
    ),
)

# ---------------------------------------------------------------------------
# Scope patterns
# ---------------------------------------------------------------------------

MULTIPLE_REQUESTS = AntiPattern(
    id="multiple_requests",
    name="Multiple Unrelated Requests",
    category=Category.SCOPE,
    severity=Severity.HIGH,
    description=(
        "The prompt appears to ask for several unrelated things at once, "
        "which dilutes focus and quality."
    ),
    suggestion=(
        "Break this into separate prompts, one per task. If tasks are related, "
        "use numbered steps to impose order."
    ),
    positive_signals=(
        re.compile(
            r"\b(also|additionally|and\s+also|on\s+top\s+of\s+that|"
            r"by\s+the\s+way|oh\s+and|plus\s+also|another\s+thing)\b",
            re.I,
        ),
    ),
)

# ---------------------------------------------------------------------------
# Keyword and regex banks for the analyzer (used for positive detection)
# ---------------------------------------------------------------------------

ROLE_KEYWORDS: tuple[str, ...] = (
    "you are",
    "act as",
    "acting as",
    "your role",
    "as a",
    "as an",
    "pretend you",
    "imagine you",
    "take the role",
    "persona",
    "you're a",
    "you're an",
    "play the role",
    "behave as",
    "respond as",
)

OUTPUT_FORMAT_KEYWORDS: tuple[str, ...] = (
    "format",
    "output as",
    "return as",
    "respond with",
    "respond in",
    "in json",
    "as json",
    "as a list",
    "as a table",
    "numbered list",
    "bullet points",
    "bulleted list",
    "markdown",
    "csv",
    "xml",
    "yaml",
    "in the form of",
    "paragraph",
    "paragraphs",
    "essay",
    "report",
    "template",
    "code block",
    "formatted as",
)

CONTEXT_SIGNALS: tuple[str, ...] = (
    "background",
    "context",
    "for context",
    "the situation is",
    "the goal is",
    "the purpose is",
    "i'm working on",
    "i am working on",
    "the project is",
    "this is for",
    "the audience is",
    "the target",
    "we need",
    "my team",
    "our company",
    "my company",
    "the client",
    "the customer",
    "the user",
    "use case",
)

CONSTRAINT_KEYWORDS: tuple[str, ...] = (
    "must",
    "should",
    "no more than",
    "no less than",
    "at most",
    "at least",
    "limit",
    "maximum",
    "minimum",
    "between",
    "within",
    "under",
    "constraint",
    "requirement",
    "do not",
    "don't",
    "avoid",
    "never",
    "always",
    "keep it",
    "make sure",
    "ensure",
    "words",
    "sentences",
    "tone",
    "formal",
    "informal",
    "casual",
    "professional",
    "academic",
    "concise",
)

EXAMPLE_KEYWORDS: tuple[str, ...] = (
    "for example",
    "example:",
    "example of",
    "e.g.",
    "such as",
    "like this:",
    "here's an example",
    "here is an example",
    "sample",
    "for instance",
    "input:",
    "output:",
    "expected:",
    "here's what i mean",
    "here is what i mean",
)

# Collect all defined anti-patterns for easy iteration
ALL_PATTERNS: tuple[AntiPattern, ...] = (
    MISSING_ROLE,
    MISSING_OUTPUT_FORMAT,
    MISSING_CONTEXT,
    VAGUE_LANGUAGE,
    AMBIGUOUS_PRONOUNS,
    NO_CONSTRAINTS,
    NO_EXAMPLES,
    MULTIPLE_REQUESTS,
)
