# Demo 10 — Alternate-route comparison (route-risk decision support)

**Situation (notional / exercise).** A logistics element must move two MRAPs from
`FOB GATEWAY` to a `Distribution yard`. Three candidate routes have been drawn by
the planner; the route-selection officer needs a defensible, quantitative basis
for choosing one. All coordinates and threat scores are notional/synthetic for
training and unit-testing — they are not real intelligence.

| Route | Character | Trade-off |
|-------|-----------|-----------|
| `alpha-direct` | Shortest MSR run, through an urban choke + bridge, full dwell | shortest distance, highest exposure |
| `bravo-bypass` | Longer rural bypass, no urban choke, lower peak threat | longest distance, lowest exposure |
| `charlie-night` | Same geometry as ALPHA but dwell minimised | same distance as ALPHA, exposure reduced by cutting dwell in the threat band |

## Run it

```bash
# Rank all three and produce a brief
convoy-or-risk demos/10-route-compare/alpha-direct \
               demos/10-route-compare/bravo-bypass \
               demos/10-route-compare/charlie-night --format markdown

# Machine-readable comparison for a downstream tool
convoy-or-risk demos/10-route-compare/* --format json --out brief.json
```

## What to expect

`bravo-bypass` is recommended despite being the **longest** route: its
exposure-minutes (threat-weighted time on route) are lowest because it avoids the
urban choke kill-zone entirely. `charlie-night` ranks ahead of `alpha-direct`
even though they share identical geometry — the only difference is dwell time in
the threat band, which is exactly what the exposure metric is designed to
surface. Both ALPHA and CHARLIE flag potential kill-zones at the town-center
choke and the canal bridge; BRAVO flags none.

## How to act

Use the ranking as decision support, not as an order. Confirm the threat overlay
against current intelligence, coordinate escort/overwatch for any flagged
kill-zone if the chosen route retains one, and obtain a risk-acceptance decision
from the approving authority for any over-policy leg before movement.
