"""Tests for the core prompt analysis engine.

Covers scoring dimensions, anti-pattern detection, edge cases, and the
overall analysis pipeline. Tests are designed to validate that the
heuristic scoring produces sensible results across a range of prompt
quality levels.
"""

from __future__ import annotations

import json

import pytest

from promptlab.analyzer import (
    AnalysisResult,
    DimensionScore,
    analyze,
    _count_words,
    _count_sentences,
)
from promptlab.reporter import render_json, render_markdown


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BAD_PROMPT = "Write me something about dogs"

VAGUE_PROMPT = "Make it good. Improve this. Do something about the thing."

MULTI_TASK_PROMPT = (
    "Write me a poem about cats. Also help me fix my Python code. "
    "And can you also create a business plan for a coffee shop?"
)

GOOD_PROMPT = (
    "You are a veterinary nutritionist writing for a pet owner blog. "
    "Write a 300-word article explaining why grain-free diets may not be "
    "suitable for all dog breeds.\n\n"
    "Target audience: First-time dog owners with no veterinary background.\n\n"
    "Requirements:\n"
    "- Use a warm, reassuring tone\n"
    "- Include at least 2 specific breed examples\n"
    "- Cite the FDA's 2019 investigation into grain-free diets and DCM\n"
    "- End with 3 actionable takeaways in a bulleted list\n"
    "- Do not recommend specific commercial brands\n\n"
    'Example of the tone I want:\n'
    '"Choosing the right food for your new furry family member can feel '
    'overwhelming, but understanding a few basics can make all the difference."'
)

MEDIUM_PROMPT = (
    "Write a blog post about the benefits of remote work. "
    "Keep it under 500 words and use a professional tone."
)


# ---------------------------------------------------------------------------
# Helper utility tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_count_words_basic(self):
        assert _count_words("hello world") == 2

    def test_count_words_empty(self):
        assert _count_words("") == 0

    def test_count_sentences_basic(self):
        assert _count_sentences("Hello. World. Test.") == 3

    def test_count_sentences_single(self):
        assert _count_sentences("Just one sentence") == 1


# ---------------------------------------------------------------------------
# Dimension score tests
# ---------------------------------------------------------------------------

class TestDimensionScore:
    def test_percentage(self):
        d = DimensionScore(name="Test", score=7.5)
        assert d.percentage == 75.0

    def test_label_excellent(self):
        assert DimensionScore(name="T", score=9.0).label == "Excellent"

    def test_label_good(self):
        assert DimensionScore(name="T", score=6.5).label == "Good"

    def test_label_fair(self):
        assert DimensionScore(name="T", score=4.0).label == "Fair"

    def test_label_weak(self):
        assert DimensionScore(name="T", score=2.5).label == "Weak"

    def test_label_poor(self):
        assert DimensionScore(name="T", score=1.0).label == "Poor"


# ---------------------------------------------------------------------------
# Full analysis tests
# ---------------------------------------------------------------------------

class TestAnalyzeBadPrompt:
    """A short, vague prompt should score poorly."""

    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze(BAD_PROMPT)

    def test_overall_score_is_low(self):
        assert self.result.overall_score < 5.0

    def test_has_anti_patterns(self):
        assert len(self.result.anti_patterns) >= 3

    def test_detects_missing_role(self):
        ids = {d.pattern.id for d in self.result.anti_patterns}
        assert "missing_role" in ids

    def test_detects_missing_output_format(self):
        ids = {d.pattern.id for d in self.result.anti_patterns}
        assert "missing_output_format" in ids

    def test_has_suggestions(self):
        assert len(self.result.suggestions) >= 1

    def test_word_count(self):
        assert self.result.word_count == 5


class TestAnalyzeGoodPrompt:
    """A well-structured prompt should score highly."""

    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze(GOOD_PROMPT)

    def test_overall_score_is_high(self):
        assert self.result.overall_score >= 7.0

    def test_structure_score_is_high(self):
        structure = next(d for d in self.result.dimensions if d.name == "Structure")
        assert structure.score >= 7.0

    def test_specificity_score_is_high(self):
        specificity = next(d for d in self.result.dimensions if d.name == "Specificity")
        assert specificity.score >= 6.0

    def test_fewer_anti_patterns(self):
        # Good prompt may still have some, but fewer than the bad one
        bad_result = analyze(BAD_PROMPT)
        assert len(self.result.anti_patterns) < len(bad_result.anti_patterns)


class TestAnalyzeVaguePrompt:
    """A prompt full of vague language should be flagged."""

    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze(VAGUE_PROMPT)

    def test_clarity_is_low(self):
        clarity = next(d for d in self.result.dimensions if d.name == "Clarity")
        assert clarity.score < 5.0

    def test_detects_vague_language(self):
        ids = {d.pattern.id for d in self.result.anti_patterns}
        assert "vague_language" in ids


class TestAnalyzeMultiTaskPrompt:
    """A prompt asking for multiple unrelated things should be detected."""

    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze(MULTI_TASK_PROMPT)

    def test_detects_multiple_requests(self):
        ids = {d.pattern.id for d in self.result.anti_patterns}
        assert "multiple_requests" in ids


class TestAnalyzeMediumPrompt:
    """A decent but not great prompt should land in the middle."""

    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze(MEDIUM_PROMPT)

    def test_overall_score_is_moderate(self):
        assert 4.0 <= self.result.overall_score <= 8.0

    def test_has_some_structure(self):
        structure = next(d for d in self.result.dimensions if d.name == "Structure")
        assert structure.score >= 2.5  # Has task verb at minimum


class TestAnalyzeEmptyPrompt:
    """An empty prompt should return minimum scores."""

    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze("")

    def test_all_dimensions_are_1(self):
        for dim in self.result.dimensions:
            assert dim.score == 1.0

    def test_overall_is_1(self):
        assert self.result.overall_score == 1.0


# ---------------------------------------------------------------------------
# Output rendering tests
# ---------------------------------------------------------------------------

class TestRenderers:
    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.result = analyze(BAD_PROMPT)

    def test_json_output_is_valid(self):
        output = render_json(self.result)
        data = json.loads(output)
        assert "overall_score" in data
        assert "dimensions" in data
        assert "anti_patterns" in data
        assert "suggestions" in data

    def test_json_score_matches(self):
        output = render_json(self.result)
        data = json.loads(output)
        assert data["overall_score"] == self.result.overall_score

    def test_markdown_contains_headers(self):
        output = render_markdown(self.result)
        assert "# PromptLab Analysis Report" in output
        assert "## Dimension Scores" in output

    def test_markdown_contains_table(self):
        output = render_markdown(self.result)
        assert "| Dimension |" in output
