# 02 — Fuel shortfall on a desert sustainment loop

**Setting (training):** A sustainment loop inside the National Training Center
(Fort Irwin, CA) maneuver box during a rotation. Coordinates are within the
public NTC training area; place names like *Tiefort City* are notional rotation
features. The truck assigned is a single **LMTV** with a deliberately short
unrefueled range entered for this leg (70 km of usable range remaining at SP).

**Where the data comes from:** Movement order / convoy brief — start point,
release points, logistics release point (LRP), and the return to the TAA, with
the assigned vehicle's remaining range.

**What to expect:** The loop is ~133 km, which exceeds the 70 km range →
**`CV-FUEL` (HIGH)**. Threat is low throughout, so no threat/escort findings.

```bash
convoy-or demos/02-fuel-shortfall/ --format console
```

**How to act:** Insert a tactical refuel (HEMTT/FARP) before the Granite Pass RP,
or swap to a longer-range platform. Note both endpoints already have fuel, so the
gap is mid-route — add an LRP refuel, not an origin top-off.
