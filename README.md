# PromptLab

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A prompt engineering analysis toolkit that scores your prompts, detects anti-patterns, and gives you actionable suggestions to improve them -- **no API key required**.

The core analysis engine runs entirely offline using rule-based heuristics, regex pattern matching, and keyword detection. An optional `--enhance` flag can call an AI provider for AI-powered rewriting, but the analysis itself needs nothing but Python.

## Installation

```bash
git clone https://github.com/orianna1510-code/promptlab.git
cd promptlab
pip install -e .
```

For AI-powered enhancement (optional):

```bash
pip install -e ".[enhance]"
```

## Quick Start

```bash
# Analyze a prompt from the command line
promptlab analyze "Write me something about dogs"

# Analyze from a file
promptlab analyze --file my_prompt.txt

# Get JSON output (great for piping into other tools)
promptlab analyze "Summarize this article" --json

# Get Markdown output (great for docs/reports)
promptlab analyze "Write a blog post" --markdown

# Pipe from stdin
echo "Fix my code" | promptlab analyze

# AI-enhanced mode (requires API key)
PROMPTLAB_API_KEY=sk-xxx promptlab analyze "Write something" --enhance
```

## Example: Weak Prompt

```bash
promptlab analyze "Write me something about dogs"
```

```
╭──────────────────────────────────────────────────────────────────╮
│                    PromptLab Analysis Report                      │
╰──────────────────────────────────────────────────────────────────╯

╭──────────────────────────── Prompt ──────────────────────────────╮
│ Write me something about dogs                                    │
╰──────────────────────────────────────────────────────────────────╯

  Words: 5    Sentences: 1

  Overall Score: 3.0/10 (Weak)
  [=========---------------------]

                          Dimension Scores
┏━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Dimension    ┃  Score  ┃  Rating  ┃ Details                     ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Clarity      │ 3.5/10  │   Weak   │ 1 vague phrase(s) detected  │
│ Structure    │ 2.5/10  │   Weak   │ Missing: role, context,     │
│              │         │          │ output format               │
│ Specificity  │ 2.0/10  │   Weak   │ No constraints; No examples │
│ Length       │ 4.0/10  │   Fair   │ 5 words -- quite short      │
└──────────────┴─────────┴──────────┴─────────────────────────────┘

Anti-Patterns Detected

  [HIGH]   Missing Context / Background
  [HIGH]   Vague / Hand-wavy Language
  [MEDIUM] Missing Role / Persona
  [MEDIUM] No Output Format Specified
  [MEDIUM] No Constraints or Boundaries
  [LOW]    No Examples Provided

Suggestions for Improvement

  1. Add context about the audience, purpose, or background.
  2. Replace vague words with specific criteria.
  3. Start with a role assignment like 'You are a...'
  4. Specify the desired output format.
  5. Add constraints (word count, tone, audience level).
  6. Include 1-2 examples of desired output.
```

## Example: Strong Prompt

```bash
promptlab analyze --file examples/good_prompt.txt
```

```
  Overall Score: 9.1/10 (Excellent)
  [===========================---]

                          Dimension Scores
┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Dimension    ┃  Score   ┃   Rating   ┃ Details                    ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Clarity      │  8.0/10  │ Excellent  │ Contains numeric specifics │
│ Structure    │ 10.0/10  │ Excellent  │ Has: role, context, task,  │
│              │          │            │ output format              │
│ Specificity  │ 10.0/10  │ Excellent  │ Strong constraints;        │
│              │          │            │ Includes examples          │
│ Length       │  8.6/10  │ Excellent  │ 108 words -- good length   │
└──────────────┴──────────┴────────────┴────────────────────────────┘

Suggestions for Improvement

  1. This is already a strong prompt. Consider adding edge-case
     handling or examples for even better results.
```

## How It Works

PromptLab analyzes prompts across four weighted dimensions, each scored from 1 to 10:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Clarity** | 30% | Is the prompt specific and unambiguous? Penalizes vague language ("make it good"), ambiguous pronouns, and extremely short prompts. Rewards numeric specifics. |
| **Structure** | 25% | Does the prompt include the four key components? Role/persona, context/background, a clear task verb, and an output format specification. Each adds 2.5 points. |
| **Specificity** | 25% | Are there constraints, examples, and quantitative details? Looks for boundary-setting keywords ("must", "at most", "tone"), example markers ("for example", "e.g."), and structured multi-line formatting. |
| **Length** | 20% | Is the prompt appropriately sized? The sweet spot is 20-300 words. Too short (under 10 words) or too long (over 500 words) gets penalized. |

The overall score is a weighted average of all four dimensions.

### Anti-Pattern Detection

Beyond scoring, PromptLab detects eight specific anti-patterns:

| Anti-Pattern | Severity | What It Catches |
|-------------|----------|-----------------|
| Missing Role/Persona | Medium | No "You are a..." or "Act as..." |
| No Output Format | Medium | No format specification (JSON, list, essay, etc.) |
| Missing Context | High | No background, audience, or purpose |
| Vague Language | High | "Make it good", "improve this", "do something" |
| Ambiguous Pronouns | Low | Starting with "Fix it" or "Improve this" with no referent |
| No Constraints | Medium | No boundaries on length, tone, or scope |
| No Examples | Low | No few-shot examples or sample output |
| Multiple Requests | High | Asking for unrelated tasks in a single prompt |

Each detected pattern includes evidence (the specific text that triggered it) and an actionable suggestion for fixing it.

## Output Formats

| Flag | Format | Use Case |
|------|--------|----------|
| *(default)* | Rich terminal | Human-readable with colors and tables |
| `--json` | JSON | Piping into scripts, CI/CD, dashboards |
| `--markdown` | Markdown | Documentation, reports, sharing |

## AI Enhancement (Optional)

When you pass `--enhance`, PromptLab sends your prompt and the analysis results to an AI provider, which rewrites the prompt to address the identified issues.

```bash
# Using OpenAI (default)
export PROMPTLAB_API_KEY=sk-your-key
promptlab analyze "Write something about AI" --enhance

# Using Anthropic
export PROMPTLAB_API_KEY=sk-ant-your-key
export PROMPTLAB_PROVIDER=anthropic
promptlab analyze "Write something about AI" --enhance

# Override the model
export PROMPTLAB_MODEL=gpt-4o
promptlab analyze "Write something about AI" --enhance
```

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `PROMPTLAB_API_KEY` | *(none)* | Your API key (required for `--enhance`) |
| `PROMPTLAB_PROVIDER` | `openai` | `openai` or `anthropic` |
| `PROMPTLAB_MODEL` | `gpt-4o-mini` / `claude-sonnet-4-20250514` | Override the default model |

## Project Structure

```
promptlab/
├── promptlab/
│   ├── __init__.py        # Package metadata
│   ├── cli.py             # Click CLI entry point
│   ├── analyzer.py        # Core analysis engine (no API needed)
│   ├── enhancer.py        # Optional AI-powered enhancement
│   ├── reporter.py        # Output formatting (text, JSON, markdown)
│   └── patterns.py        # Anti-pattern definitions and detection rules
├── tests/
│   └── test_analyzer.py   # 31 test cases covering all analysis paths
├── examples/
│   ├── bad_prompt.txt     # Sample weak prompt for demo
│   └── good_prompt.txt    # Sample strong prompt for demo
├── pyproject.toml         # Project config and dependencies
├── LICENSE                # MIT
└── README.md
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
