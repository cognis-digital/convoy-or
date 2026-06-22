# 03 — Permissive port run (Camp Lemonnier → Doraleh)

**Setting (real, permissive):** A routine logistics run from **Camp Lemonnier**
(the U.S. base co-located with Djibouti–Ambouli airport) to the **Doraleh
Multipurpose Port** to receive containerized sustainment. All three nodes are
well-documented public locations; the run is short and on a paved main road
(RN-1 corridor) in a permissive environment.

**Where the data comes from:** A port-call movement request — base SP, the
RN-1/Ambouli junction, and the port gate, with an armored **MTVR** assigned.

**What to expect:** ~10 km total, low threat, fuel at both ends → no policy
breaches. You get the single **`CV-OK` (VERY_LOW)** baseline finding.

```bash
convoy-or demos/03-djibouti-port-run/ --format console
```

**How to act:** This is the "green" baseline — useful as a CI smoke check. Gate a
pipeline with `--fail-on high` and confirm it exits 0:

```bash
convoy-or demos/03-djibouti-port-run/ --format json --fail-on high ; echo "exit=$?"
```

Also try the map export to drop the route into geojson.io / QGIS:

```bash
convoy-or-map demos/03-djibouti-port-run/ --out route.geojson
```
