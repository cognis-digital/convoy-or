# 08 — Starter template (and the no-plan error path)

**Setting:** This directory ships **`plan.template.json`** instead of a
`plan.json`. It is a fill-in-the-blanks starting point showing every supported
field with safe placeholder values.

**Where the data comes from:** Nowhere yet — that's the point. Copy the template,
fill in your own movement order, and run the tool.

**What to expect:** Run the tool against this directory *as shipped* and, because
there is no `plan.json`, you get the diagnostic **`CV-NOPLAN` (MODERATE)** —
useful for confirming your wrapper handles the missing-input case.

```bash
convoy-or demos/08-noplan-template/ --format console
```

**How to act:** Build your own plan from the template, then re-run:

```bash
cp demos/08-noplan-template/plan.template.json demos/08-noplan-template/plan.json
# edit stops/vehicles ...
convoy-or demos/08-noplan-template/ --format json
```

Field reference: each stop is `{name, lat, lon, dwell_min, threat_score (0-1),
fuel_available, choke_point}`; each vehicle is
`{id, type, range_km, fuel_per_km, armored}`; plan-level knobs are
`max_threat_per_leg` (hard ceiling → `CV-THREAT`) and
`escort_required_above_threat` (→ `CV-ESCORT`).
