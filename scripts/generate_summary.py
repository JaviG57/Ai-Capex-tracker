"""
Generates the "Daily Summary" tab content by sending pre-computed trend
deltas (NOT raw history -- see storage.compute_deltas) to Claude Sonnet 5.

Why deltas and not raw series: dumping 30 days of history per metric would
run several thousand tokens per company and cost real money for no benefit.
Computing % changes in Python first keeps the prompt to ~3-4k tokens/day
regardless of how much history has piled up, at a cost of a few dollars a
year -- see the pricing discussion this repo's setup conversation covered.
"""
import os
import json
import anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You write the lead item on a personal dashboard that \
tracks AI-capex-related signals (hiring, spending signals, compute \
utilization, power/buildout) across major AI-infrastructure companies. \
The reader is financially and data-literate -- write with real specificity \
(name companies, cite the actual percentages), not a dumbed-down gloss.

You will receive a JSON object of metrics, each with a `current` value and \
percent changes over 1, 7, and 30 days (missing keys mean not enough \
history yet -- don't mention data that isn't there).

Cover three things, in this order, as flowing prose (not headers/bullets):

1. What changed today/this week. The 3-5 most notable individual moves, \
prioritizing 7d/30d changes over 1d ones (a single day's move on a \
low-volume metric like job postings or 8-K counts is noise, not signal --
say so explicitly if you mention one at all).

2. Similarities across companies. Are multiple companies moving the same \
way on the same metric (e.g. hiring cooling at several hyperscalers \
simultaneously, or a synchronized pickup in AI-titled postings across \
chipmakers)? Synchronized moves across independent companies are more \
informative than any single company's move -- call these out by name.

3. Patterns across the combined signals. Look across metric categories, \
not just within one (e.g. hiring decelerating while 8-K/capex-signal \
activity holds steady or accelerates would be a notable divergence worth \
flagging as a thing to watch, not a conclusion to draw).

Ground rules:
- 200-350 words total, plain prose, no headers, no bullet lists.
- Never claim causation between two metrics unless it's a plainly \
mechanical relationship (e.g. a stock move following an 8-K the same day). \
Correlation across noisy proxies -- even a striking one -- is not evidence \
of a causal link; frame cross-metric observations as "worth watching," \
not as conclusions.
- Distinguish clearly between "several companies moved together" (an \
observation you can state plainly) and "X caused Y across companies" (a \
claim you should not make).
- If nothing notable moved anywhere, say so plainly instead of \
manufacturing a narrative out of noise.
"""


def generate(deltas: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "(No ANTHROPIC_API_KEY set -- skipping daily summary generation.)"
    if not deltas:
        return "(Not enough data yet to generate a summary -- check back after a few days of collection.)"

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Today's metric deltas:\n{json.dumps(deltas, indent=2)}",
        }],
    )
    return "".join(block.text for block in message.content if block.type == "text")
