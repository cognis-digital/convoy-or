# 04 — Defile + bridge choke points (JMRC Hohenfels)

**Setting (training):** A movement through restricted terrain during a rotation
at the Joint Multinational Readiness Center (Hohenfels Training Area, Germany).
Coordinates are within the public training area; the defile entry and bridge
crossing are notional rotation features. Threat is *moderate* at the chokes
(0.45–0.50) — below the hard per-leg policy (0.70) but above the escort
threshold the planner set (0.40).

**Where the data comes from:** A route recon overlay — two restricted-terrain
points (defile, bridge) flagged as choke points, each with a dwell estimate.

**What to expect:** Choke points present → **`CV-CHOKE` (MODERATE)**; at least
one leg at/above the escort threshold → **`CV-ESCORT` (MODERATE)**. No fuel or
hard-threat breach (a long-range Boxer, short distance).

```bash
convoy-or demos/04-mountain-chokepoint/ --format markdown
```

**How to act:** Pre-coordinate near/far-side security and overwatch for the
defile and bridge, and minimize dwell at both. Assign the escort the planner
flagged. Export the legs to a map to brief the choke points visually:

```bash
convoy-or-map demos/04-mountain-chokepoint/ | python -m json.tool | head
```
