# 05 — Threat over policy on a contested corridor (exercise)

**Setting (exercise/notional):** A resupply push along a corridor where an
intelligence overlay marks an IED belt. All node names are exercise constructs
(*FOB ANVIL*, *Phase Line BLUE*, *Objective WAREHOUSE*) and coordinates are
notional — this is a planning drill, not a real operation. One leg's threat
score (0.82) exceeds the unit's hard per-leg policy ceiling (0.70).

**Where the data comes from:** The S2 threat overlay fused onto the route — each
node carries a threat score; the IED-belt node drives the leg threat.

**What to expect:** A leg above the hard ceiling → **`CV-THREAT` (HIGH)**, and
because legs also exceed the escort threshold → **`CV-ESCORT` (MODERATE)**.

```bash
convoy-or demos/05-high-threat-corridor/ --format console
```

**How to act:** `CV-THREAT` is a *stop-and-decide* trigger: reroute around the
IED belt, raise the escort posture (route clearance package), or postpone until
the overlay changes. Gate go/no-go in a planning pipeline:

```bash
convoy-or demos/05-high-threat-corridor/ --format sarif --fail-on high ; echo "exit=$?"
```
