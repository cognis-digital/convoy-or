# 09 — Worst-case corridor: every finding fires (exercise)

**Setting (exercise/notional):** A deliberately stressing planning drill where a
single route trips **all four** policy findings at once. Node names
(*FOB SENTINEL*, *Objective KEYSTONE*) and coordinates are exercise constructs.
The assigned platform has very little remaining range (60 km), the corridor runs
through three canalizing choke points, and one leg's threat (0.88) blows past the
hard ceiling.

**Where the data comes from:** A fused planning product — terrain (canalized
crossings flagged as chokes), S2 threat overlay, and a degraded vehicle range —
combined to demonstrate the full finding set.

**What to expect:** The most severe demo in the set:
- **`CV-FUEL` (HIGH)** — ~127 km vs 60 km range
- **`CV-THREAT` (HIGH)** — a leg at 0.88 > 0.70 ceiling
- **`CV-ESCORT` (MODERATE)** — legs above the escort threshold
- **`CV-CHOKE` (MODERATE)** — three choke points

This pushes the composite risk into the **Low** band (it is the highest score
across the demo set).

```bash
convoy-or demos/09-max-risk-corridor/ --format markdown
```

**How to act:** This is a no-go as planned. Treat it as a checklist:
refuel/replatform (FUEL), reroute or postpone (THREAT), assign route clearance +
escort (ESCORT), and pre-clear the three chokes (CHOKE). Use it as a CI fixture
to prove `--fail-on high` correctly blocks:

```bash
convoy-or demos/09-max-risk-corridor/ --format sarif --fail-on high ; echo "exit=$? (expect 1)"
```
