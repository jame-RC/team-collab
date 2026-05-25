"""Quick integration test: call DeepSeek API via Anthropic-compatible endpoint.

Verifies that the reviewer prompt + DeepSeek produces a valid ReviewResult JSON.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import anthropic

API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/anthropic")
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """\
You are a strict academic reviewer. Evaluate the submitted artifact against the task contract.
Score on 5 dimensions (0-20 each, total 0-100):
1. contract: Does it fulfill the task requirements?
2. brief: Does it address the project brief?
3. glossary: Does it use defined terms correctly?
4. continuity: Is it consistent with upstream artifacts?
5. evidence: Does it provide supporting evidence/data?

Output ONLY valid JSON in this exact format:
{
  "verdict": "approved" or "needs_revision" or "rejected",
  "score": <total 0-100>,
  "comments": [{"locator": "", "severity": "info", "message": "..."}],
  "dimensions": {"contract": N, "brief": N, "glossary": N, "continuity": N, "evidence": N}
}
"""

USER_MESSAGE = """\
## Task Contract
```json
{
  "task_id": "task-001",
  "title": "Campus energy audit report",
  "brief": "Investigate current campus energy usage, identify top 3 waste areas, provide data-backed recommendations",
  "owner": "bob",
  "deps": [],
  "status": "submitted"
}
```

## Submitted Artifact Content
# Campus Energy Audit Report

## Executive Summary
Based on a comprehensive survey of Building A, B, and the Library during March 2026, we identified three major energy waste areas.

## Findings

### 1. HVAC Over-conditioning (38% of total waste)
- Average indoor temperature: 18C in summer (vs 26C recommended)
- HVAC systems run 24/7 including unoccupied hours (22:00-06:00)
- Estimated annual waste: 450,000 kWh

### 2. Lighting Inefficiency (29% of total waste)
- 60% of fixtures are T8 fluorescent (vs LED)
- No occupancy sensors in 80% of classrooms
- Estimated annual waste: 340,000 kWh

### 3. IT Equipment Standby (18% of total waste)
- 1,200 desktop computers never fully powered off
- Lab servers running at 15% average utilization
- Estimated annual waste: 210,000 kWh

## Recommendations
1. Install smart HVAC scheduling (ROI: 14 months)
2. Replace T8 with LED + add occupancy sensors (ROI: 18 months)
3. Implement auto-shutdown policies for desktops (ROI: 3 months)

## Data Sources
- Smart meter readings (March 2026)
- Facility management interviews (n=5)
- Thermal imaging survey (Building A, B)

## Glossary
```json
{"entries": {"HVAC": {"definition": "Heating, Ventilation, and Air Conditioning"}, "kWh": {"definition": "Kilowatt-hour, unit of energy"}}}
```
"""


def main() -> None:
    print(f"Connecting to DeepSeek API at {BASE_URL}")
    print(f"Model: {MODEL}")
    print("-" * 60)

    client = anthropic.Anthropic(base_url=BASE_URL, api_key=API_KEY)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_MESSAGE}],
        )
    except Exception as e:
        print(f"API call failed: {e}")
        sys.exit(1)

    raw_text = response.content[0].text
    print("Raw API response:")
    print(raw_text)
    print("-" * 60)

    try:
        review = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            review = json.loads(raw_text[start:end])
        else:
            print("FAILED: Could not parse response as JSON")
            sys.exit(1)

    print("\nParsed ReviewResult:")
    print(json.dumps(review, indent=2, ensure_ascii=False))

    verdict = review.get("verdict")
    score = review.get("score")
    print(f"\nVerdict: {verdict}")
    print(f"Score: {score}/100")

    assert verdict in ("approved", "needs_revision", "rejected"), f"Invalid verdict: {verdict}"
    assert isinstance(score, (int, float)) and 0 <= score <= 100, f"Invalid score: {score}"
    print("\n[PASS] DeepSeek API integration works correctly!")


if __name__ == "__main__":
    main()
