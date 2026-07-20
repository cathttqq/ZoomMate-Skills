---
name: meeting-diff-analysis
description: >-
  Compares two occurrences of the same recurring Zoom meeting series and produces a
  side-by-side diff of what changed between them — topics and decisions, action-item
  status (new / carried-over / done / dropped), attendance and participation, logistics
  and sentiment, plus a computed meeting-efficiency score for each occurrence so you can
  see whether the meeting is getting more or less effective over time. Delivers the result
  as a stylish, self-contained HTML poster report with interactive charts (efficiency scores
  up top, parameter visualizations in the middle, comparison tables below, key insights at
  the bottom). Use this whenever someone wants to understand how a recurring meeting evolved
  from one instance to the next: "what changed since last week's standup", "compare this
  sprint review to the previous one", "diff the last two instances of my 1:1 with Sam",
  "how did today's team sync differ from last time", "did we close the action items from
  the previous meeting", "is our weekly getting more efficient". Trigger it even when the
  user doesn't say the word "compare" — any request to see differences, progress,
  carry-over, or efficiency between two meetings in the same recurring series belongs here.
  Works in ZoomMate (native meeting access) and in Claude Code (via a connected Zoom
  tool/MCP or user-provided transcripts).
---

# Meeting Diff Analysis

Recurring meetings drift. The agenda shifts, action items pile up or get closed, people
come and go, and the energy in the room changes. This skill takes two occurrences of the
**same recurring series** and shows, at a glance, what actually changed between them —
including whether the meeting is getting more or less efficient — so the user can walk
into the next one already knowing where things stand.

## What "two instances" means

An **instance** (occurrence) is one dated meeting within a recurring series (e.g. the
weekly team sync on Jul 2 vs. Jul 9). Unless the user names specific dates or occurrences,
default to **the two most recent instances** of the series, treating the older one as the
*baseline* ("before") and the newer one as the *current* ("after"). The diff always reads
baseline → current, so "new", "dropped", and "closed" are all relative to that direction.

If the user says something ambiguous like "compare my standups", ask which series and,
if it's not obvious, confirm the two occurrences before spending effort gathering data.

## Workflow

### 1. Identify the series and the two occurrences
Pin down which recurring series and which two dated instances. Default to the latest two
if the user doesn't specify. Note their dates — you'll use them as column headers.

### 2. Gather the data for each occurrence
You need comparable raw material for **both** meetings. Use whatever meeting-data access
the environment provides — in ZoomMate this is native; in Claude Code it may be a
connected Zoom connector/MCP, or files/text the user supplies. For each occurrence, try to
collect:

- **Transcript** — the richest source; drives topics, decisions, action items,
  participation, sentiment, and the efficiency score.
- **AI Companion / meeting summary** — a fast path to topics, decisions, and action items
  when available. Cross-check it against the transcript rather than trusting it blindly.
- **Participants list** — who was invited and who actually attended, with join/leave if
  available.
- **Chat messages** — often where links, decisions, and side action items live.
- **Metadata** — start time, duration, meeting title.

If you can only get data for one of the two occurrences, don't fabricate the other side.
Say what's missing and offer to proceed with a partial comparison or wait for the data.
If no meeting access exists at all, tell the user how to provide it (connect a Zoom tool,
or paste/drop the two transcripts) rather than guessing.

### 3. Extract the comparison dimensions for each occurrence
Work through the transcript/summary for each meeting and pull out:

- **Topics & decisions** — the main discussion threads and any decisions reached.
- **Action items** — each commitment, its owner, and (if discernible) status. You'll
  reconcile these across meetings in step 4.
- **Attendance & participation** — who attended vs. was absent, and a rough sense of who
  drove the conversation (talk time / number of contributions) if the transcript supports it.
- **Logistics & sentiment** — duration, start time, and overall tone/engagement, with a
  concrete signal for any sentiment claim (e.g. "several unresolved debates", "lots of
  quick agreement") rather than a bare adjective.
- **Efficiency inputs** — the five values needed for the efficiency score below.

### 4. Reconcile action items across the two meetings
This is one of the highest-value parts of the diff, so do it deliberately. Match action
items between the baseline and current meeting by owner + topic, allowing for reworded
phrasing (the same commitment rarely appears verbatim twice). Classify each as:

- **Carried over** — raised in the baseline, still open/discussed in the current meeting.
- **Closed / done** — raised earlier and reported complete in the current meeting.
- **New** — first appears in the current meeting.
- **Dropped** — raised in the baseline and never mentioned again (flag these; they're
  easy to lose).

### 5. Compute the efficiency score for each occurrence
The efficiency score captures how much a meeting accomplishes relative to its length and
redundancy. A meeting that drives many outcomes across engaged participants in less time,
without rehashing old ground, scores higher. Compute it for **both** occurrences so the
score itself becomes part of the diff.

```text
Efficiency Score (E) = k * (T * R * P) / (M * (1 + Rt))
```

Where, for a single occurrence:
- `T` = number of **unique topics** discussed
- `R` = number of **actionable results or decisions** made
- `P` = number of **participants who actively spoke** (not just attended)
- `M` = **total meeting duration** in minutes
- `Rt` = number of **repeated topics** — topics also covered in the baseline occurrence,
  i.e. rehashed rather than new ground. For the baseline itself, use 0 unless the user
  supplies an earlier meeting to measure repetition against.
- `k` = optional normalization constant; default `k = 1` and state it if you change it.

Keep `M` in minutes for both occurrences so the two scores are comparable. Show your
inputs, not just the final number — the value only means something when the user can see
what fed it. If a required input can't be determined from the available data, say so and
skip the score rather than guessing at `T`, `R`, `P`, `M`, or `Rt`.

Once you've derived the five inputs for each occurrence, **run the bundled script rather
than doing the arithmetic by hand** — it's deterministic and reports the delta for you:

```bash
python3 scripts/efficiency.py \
  --baseline T=5,R=2,P=4,M=60,Rt=0 \
  --current  T=6,R=3,P=5,M=90,Rt=1
```

This prints both scores and the signed delta (up / down / flat). For a single occurrence,
use the flag form: `python3 scripts/efficiency.py --T 6 --R 3 --P 5 --M 90 --Rt 1`. Pass
`--k` to change the normalization constant (default 1.0). The script refuses invalid input
(e.g. `M <= 0`) instead of emitting a bogus number, which is exactly the guess you want to
avoid.

**Worked example.** A meeting with 6 unique topics, 3 results, 5 active speakers, 90
minutes, and 1 repeated topic (k = 1) yields `E = (6 * 3 * 5) / (90 * (1 + 1)) = 0.5`.

### 6. Produce the HTML report
Render the comparison as a **stylish, self-contained HTML poster** built from the bundled
template — don't just dump markdown into the chat. The template gives every report the
same visual design, so your job is to fill in content, not design CSS. See the output
section below for exactly how.

## Output format

The deliverable is a single `.html` file generated from `assets/report_template.html`.
That template is self-contained (all CSS and JavaScript are inline — no external assets),
so the file the user gets is portable and shareable on its own. It renders as a poster:

1. **Dark gradient header** with series name and date range.
2. **Efficiency score hero cards** — baseline and current scores overlapping the header,
   with a delta pill between them and a proportional fill bar under each score.
3. **Parameter charts** — four canvas-based visualizations (no external libraries):
   - Grouped bar chart: T, R, P (productivity inputs)
   - Grouped bar chart: M, Rt (cost inputs)
   - Radar chart: T / R / P normalized comparison
   - Dual semicircle gauge: efficiency score E for each meeting
4. **Side-by-side comparison table** — qualitative dimensions.
5. **Efficiency formula breakdown table** — the five inputs and final E score.
6. **Action item cards** — each item as a styled card (not a table row).
7. **Key insights list** — 3–6 headline takeaways.

### How to build it
1. Read `assets/report_template.html`.
2. Replace every `{{PLACEHOLDER}}` with real content, then write the result to a new file
   (e.g. `<series>-diff-<current-date>.html`). Don't edit the template in place.
3. Tell the user the path and offer to open it.

The placeholders:

| Placeholder | Fill with |
|---|---|
| `{{SERIES_NAME}}` | The recurring series name |
| `{{BASELINE_DATE}}` / `{{CURRENT_DATE}}` | The two occurrence dates (used as column headers too) |
| `{{BASELINE_SCORE}}` / `{{CURRENT_SCORE}}` | The efficiency scores from the script, e.g. `0.67` |
| `{{BASELINE_SCORE_PCT}}` / `{{CURRENT_SCORE_PCT}}` | Integer 0–100 for the score fill bar. Set the higher score to `100` and the lower to `round(lower/higher*100)`. E.g. baseline=0.50, current=0.67 → baseline_pct=75, current_pct=100 |
| `{{BASELINE_T}}` / `{{CURRENT_T}}` | Integer — unique topics discussed |
| `{{BASELINE_R}}` / `{{CURRENT_R}}` | Integer — actionable results / decisions |
| `{{BASELINE_P}}` / `{{CURRENT_P}}` | Integer — participants who actively spoke |
| `{{BASELINE_M}}` / `{{CURRENT_M}}` | Integer — meeting duration in minutes |
| `{{BASELINE_RT}}` / `{{CURRENT_RT}}` | Integer — repeated topics (Rt) |
| `{{DELTA_VALUE}}` | Signed delta, e.g. `+0.17` or `−0.17` |
| `{{DELTA_CLASS}}` | `up`, `down`, or `flat` — colors the delta pill |
| `{{DELTA_ARROW}}` | `↑`, `↓`, or `→` to match the class |
| `{{DELTA_WORD}}` | `improved`, `declined`, or `unchanged` |
| `{{BASELINE_TREND_CLASS}}` / `{{CURRENT_TREND_CLASS}}` | Leave `flat` on baseline; set `up`/`down` on current to hint the direction; optional |
| `{{SIDE_BY_SIDE_ROWS}}` | One `<tr>` per dimension (topics & decisions, attendance, participation, duration & timing, sentiment / energy) |
| `{{EFFICIENCY_ROWS}}` | The T / R / P / M / Rt rows plus a final `<tr class="total">` for the score |
| `{{ACTION_ITEM_ROWS}}` | One `.ai-card` div per action item (see card markup below) |
| `{{INSIGHTS}}` | 3–6 `<li>` items, most significant first, leading with the efficiency trend if it moved meaningfully |

**Action item card markup** (replaces the old `<tr>` format):
```html
<div class="ai-card">
  <span class="tag closed">Closed</span>
  <div class="ai-body">
    <p class="ai-text">Description of the action item</p>
    <p class="ai-owner">Owner name</p>
  </div>
</div>
```
Tag classes: `closed` / `carried` / `new` / `dropped`.

The template's HTML comments show the exact markup expected for each region — follow
them so the styling holds. Keep table cells tight; this is a scan-in-ten-seconds artifact,
not a transcript. Push detail into the Key insights list only when it's genuinely
load-bearing.

If a dimension's data was unavailable for one meeting, put
`<span class="na">not available</span>` in that cell rather than leaving it blank or
inventing it — a visible, honest gap beats a confident guess. If an efficiency input is
missing so no score can be computed, say so in Key insights and set the hero scores to
`n/a` with a `flat` delta rather than fabricating numbers. For the chart data placeholders,
use `0` as a fallback when a value is genuinely unknown (the charts will still render).

## Guardrails

- **Same series only.** Comparing two unrelated meetings produces noise, not signal. If
  the two occurrences don't look like the same recurring series, say so before proceeding.
- **Show the efficiency inputs.** The score is only trustworthy when the user can see the
  five values behind it, so always present the breakdown alongside the number.
- **Attribute sentiment to evidence.** "Tense" or "upbeat" claims should point at
  something in the transcript. Meeting tone is easy to misread, so let the user see why.
- **Match people carefully.** The same person can appear under different display names
  across occurrences. Reconcile obvious variants; flag genuinely ambiguous ones.
- **Don't invent an action-item status.** If the transcript doesn't say whether something
  got done, mark it carried-over, not closed.
