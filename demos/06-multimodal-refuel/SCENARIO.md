# 06 — Long haul with mixed fleet and a mid-route CSC

**Setting (permissive sustainment):** A line-haul out of **Camp Arifjan** (Kuwait)
up the main supply route toward a forward distribution point, with a Convoy
Support Center (CSC) mid-route. The serial is a *mixed fleet*: a HEMTT
(480 km range) and an M915 line-haul tractor (800 km range). Coordinates follow
the Highway 80 / MSR corridor; the CSC and FDP are notional.

**Where the data comes from:** A line-haul movement order with the assigned
serial's two platforms and the planned halt at the CSC.

**What to expect:** The route is ~192 km. The **fleet range is governed by the
longest-range vehicle** (800 km), so there is no fuel breach, and threat stays
low → **`CV-OK` (VERY_LOW)**. The interesting output is the `meta.refuel_stops`
list (three fuel nodes including the CSC) — confirming a refuel plan exists.

```bash
convoy-or demos/06-multimodal-refuel/ --format json | jq '.meta.refuel_stops, .meta.total_km'
```

**How to act:** Use this as the planning template for line-haul: confirm the CSC
is on the manifest, and watch the `needs_refuel` flag if you later swap the
M915 out — losing the long-range platform would flip this to `CV-FUEL`.
