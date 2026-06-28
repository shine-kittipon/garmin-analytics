"""
report.py — Generate a weekly coaching report via the Anthropic API.

Reads the current database via features.py, builds the CoachSummary,
and asks Claude to produce a structured markdown coaching report.
The report is written to data/reports/weekly-YYYY-Www.md and committed
by the GitHub Actions workflow every Monday.

Usage:
    python -m coach.report
    python -m coach.report --as-of 2026-06-23   # specific week
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import anthropic

from .features import summary_as_dict

PROMPTS_DIR = Path(__file__).parent / "prompts"
REPORTS_DIR = Path(__file__).parents[1] / "data" / "reports"

# claude-sonnet-4-6 is fast and cost-effective for weekly reports;
# swap to claude-opus-4-8 for deeper multi-session analysis if needed.
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


def generate_report(as_of: str | None = None) -> str:
    """Call the Anthropic API and return the coaching report as a markdown string."""
    as_of = as_of or date.today().isoformat()

    summary = summary_as_dict(as_of)
    system_prompt = (PROMPTS_DIR / "coach.md").read_text(encoding="utf-8")

    user_message = (
        f"Today is {as_of}.\n\n"
        "Here is the athlete's data summary (JSON):\n\n"
        f"```json\n{json.dumps(summary, indent=2, default=str)}\n```\n\n"
        "Please produce the weekly coaching report."
    )

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def save_report(content: str, as_of: str | None = None) -> Path:
    """Write the report to data/reports/weekly-YYYY-Www.md and return the path."""
    as_of = as_of or date.today().isoformat()
    week = date.fromisoformat(as_of).strftime("%Y-W%W")
    path = REPORTS_DIR / f"weekly-{week}.md"
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="Generate weekly AI coaching report")
    p.add_argument("--as-of", help="Reference date YYYY-MM-DD (defaults to today)")
    args = p.parse_args()

    as_of = args.as_of
    print(f"Generating weekly coaching report (as of {as_of or date.today()})…")
    content = generate_report(as_of)
    path = save_report(content, as_of)
    print(f"Report saved: {path}")
    print()
    print(content)


if __name__ == "__main__":
    main()
