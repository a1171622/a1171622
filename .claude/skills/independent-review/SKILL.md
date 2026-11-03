---
name: independent-review
description: Run the reviewer role - a fresh subagent that checks a planned Home Assistant, hub or model change against its spec, live entity ids, known pitfalls and the engineer's numbers before it ships. Use before any non-trivial change goes live.
---

# Independent review pass

Wing's project rule: before a change ships, a separate check confirms it does what the plan said, breaks nothing that
already works, and that the numbers hold up. The coder re-reading its own work does not count.

## How to run it

1. Write the reviewer's brief. Give it **the spec and the diff, not your reasoning**, so it isn't anchored on your
   conclusion. Include:
   - What the change must do, in Wing's words if possible, and what must not change.
   - The diff (or the new file), and where the live file is in HA.
   - The relevant HANDOFF.md section names (`claude/HANDOFF.md` in HA) so it can read the rules itself.
   - For an engineering change: the data, the script and the claimed result, so it can re-run the numbers.
   - For a hub change: the before/after screenshots.
2. Launch it with the Agent tool as a fresh agent (general-purpose). Read-only: it must not write to HA.
3. Ask it to return a verdict PASS / PASS WITH FIXES / FAIL and a list of findings, each with a concrete failure
   scenario (inputs or state -> wrong outcome).

## What the reviewer checks

- **Does what the spec said**, including edge cases: restarts mid-run, the free window 11:00-13:58, midnight and 01:00
  boundaries, nobody home, unavailable sensors, the car away, the battery near 0 % or 100 %.
- **Entity ids exist live** (eval_template), and the misleading aircon names are mapped right.
- **Syntax**: YAML (quoted `"on"`/`"off"`), Jinja renders on live state, JS parses; the diff applies to the live sha.
- **Breaks nothing**: other automations that touch the same entities (Hold, free hours, morning comfort, fan/swing
  memory, car charging, safety caps). Standing constraints in HANDOFF §1 (e.g. never stop the car for the house,
  lighting automations untouched, safety not weakened).
- **Numbers**: units, Melbourne time zone, tariff windows, that a backtest uses days the model wasn't tuned on.
- **Does it need Wing's OK**: restart, cost, visible change, deleting something.

## After the review

Fix the findings, and re-review once if a fix was not trivial (at most two rounds, then go back to the plan). Say in
the PROGRESS_LOG entry and in the message to Wing that a separate review passed, and what it could not check.
