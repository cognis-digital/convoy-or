# 07 — HADR flood-relief convoy with bridge choke points

**Setting (humanitarian):** A foreign disaster-relief (HADR) aid convoy moving
relief supplies from a port staging yard to an affected village after flooding.
Two bridges are the limiting features: a single-lane bridge and a
flood-damaged bridge, both flagged as choke points. Threat is *moderate*
(0.45) — reflecting crowd/civil-control friction at the bridges, not combat.
Coordinates are in a coastal metro area; the bridges and PODs are notional.

**Where the data comes from:** A relief-movement plan — staging yard, a
distribution hub at a school, two bridges, and the point of distribution (POD)
at the affected village, with civil-assessment threat scores.

**What to expect:** Both bridges flagged → **`CV-CHOKE` (MODERATE)**, and the
bridge legs hit the escort threshold (0.40) → **`CV-ESCORT` (MODERATE)**. No
fuel/hard-threat breach.

```bash
convoy-or demos/07-hadr-flood-relief/ --format console
```

**How to act:** Stage traffic-control at each bridge, minimize dwell (the
flood-damaged bridge has a load/single-vehicle constraint), and coordinate a
civil-affairs / host-nation police escort rather than a combat escort. Map it
for the relief coordination cell:

```bash
convoy-or-map demos/07-hadr-flood-relief/ --out flood-relief.geojson
```
