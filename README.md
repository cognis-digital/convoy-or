# convoy-or — Military convoy / logistics OR

[![CI](https://github.com/cognis-digital/convoy-or/workflows/CI/badge.svg)](https://github.com/cognis-digital/convoy-or/actions)
[![Classification](https://img.shields.io/badge/classification-UNCLASSIFIED-green.svg)](./UPSTREAM.md)

> Plan and audit convoys: route distance, fuel, threat exposure, escort requirements, choke points. OR-Tools compatible.

## Usage — step by step

`convoy-or` evaluates a convoy/logistics plan against policy bounds (fuel, threat exposure, escort, chokepoints) and emits findings in your choice of format.

1. **Install** (from PyPI or a local checkout):

   ```bash
   pip install cognis-convoy-or      # or: pip install -e .
   convoy-or --version
   ```

2. **Run a scan** — point it at a directory containing a `plan.json` (or at the file's parent). The positional `target` defaults to `.`:

   ```bash
   convoy-or ./mission --format console
   ```

3. **Get machine-readable output** — switch the format and write to a file. Supported: `console`, `json`, `markdown`, `sarif`, `oscal`:

   ```bash
   convoy-or ./mission --format json --out convoy-findings.json
   ```

4. **Read the result** — each finding has an id (e.g. `CV-FUEL`, `CV-THREAT`, `CV-ESCORT`, `CV-CHOKE`), a NIST-800-30 severity, and a location. Inspect the JSON:

   ```bash
   jq '.findings[] | {id, severity, message}' convoy-findings.json
   ```

5. **Gate it in CI** — make the process exit non-zero when anything at/above a severity is found via `--fail-on` (`very_high`|`high`|`moderate`|`low`|`none`):

   ```bash
   convoy-or ./mission --format sarif --out convoy.sarif --fail-on high \
     --classification "UNCLASSIFIED//FOR PUBLIC RELEASE"
   ```

## Upstream

Forks / wraps **https://github.com/google/or-tools**. See [`UPSTREAM.md`](./UPSTREAM.md) for the
licensing posture, supported commits, and how to upgrade.

## What this adds for military / IC use

- Convoy plan evaluator (distance / fuel / threat)
- Escort-required check above configurable threat threshold
- Choke-point dwell minimization
- OR-Tools VRP integration (when installed)

## Install

```bash
# Shared library (only once for the whole ecosystem):
pip install -e ../../shared

# This tool:
pip install -e .
```

## Demos — real-use-case scenarios

Each `demos/<NN-name>/` directory has a `plan.json` in the tool's real input
format plus a `SCENARIO.md` (where the data came from, what to expect, the exact
run command, and how to act). They span permissive, training, exercise, and
humanitarian situations and collectively exercise every finding type.

| Demo | Situation | Fires |
|------|-----------|-------|
| `01-mixed` | Mountain route with chokes + high threat | `CV-THREAT` `CV-CHOKE` `CV-ESCORT` |
| `02-fuel-shortfall` | NTC desert loop, short-range LMTV | `CV-FUEL` |
| `03-djibouti-port-run` | Permissive Camp Lemonnier → Doraleh port run | `CV-OK` (green baseline) |
| `04-mountain-chokepoint` | JMRC defile + bridge choke points | `CV-CHOKE` `CV-ESCORT` |
| `05-high-threat-corridor` | IED-belt overlay over the hard ceiling (exercise) | `CV-THREAT` `CV-ESCORT` |
| `06-multimodal-refuel` | Line-haul with a mixed fleet + mid-route CSC | `CV-OK` (refuel plan in meta) |
| `07-hadr-flood-relief` | HADR aid convoy over flood-damaged bridges | `CV-CHOKE` `CV-ESCORT` |
| `08-noplan-template` | Fill-in starter template + the no-plan error path | `CV-NOPLAN` |
| `09-max-risk-corridor` | Worst-case: every finding at once (exercise) | `CV-FUEL` `CV-THREAT` `CV-ESCORT` `CV-CHOKE` |
| `10-route-compare` | Three alternate routes ranked by exposure (decision support) | `convoy-or-risk` comparison |

```bash
convoy-or demos/01-mixed/
convoy-or demos/09-max-risk-corridor/ --format sarif --fail-on high   # exits 1
```

> All node names/coordinates in the contested/exercise demos are notional
> planning constructs. Demos are framed for **authorized planning, training, and
> humanitarian use** only.

Outputs are available in five formats — all respect an operator-supplied
classification banner (passed via `--classification`):

```bash
convoy-or <target> --format=console     # default
convoy-or <target> --format=json
convoy-or <target> --format=sarif       # for code-scanning pipelines
convoy-or <target> --format=markdown    # for PRs / briefings
convoy-or <target> --format=oscal       # OSCAL Assessment Results skeleton
```

## Map export — GeoJSON (RFC 7946)

convoy-or is the geospatial member of the suite: every stop has a lat/lon and
every leg is a line on a map. The `convoy-or-map` command renders a plan as a
standard **RFC 7946 `FeatureCollection`** you can drop straight into QGIS,
kepler.gl, Leaflet, [geojson.io](https://geojson.io), or an ATAK/CivTAK overlay:

```bash
convoy-or-map demos/04-mountain-chokepoint/                 # GeoJSON to stdout
convoy-or-map demos/07-hadr-flood-relief/ --out route.geojson
```

Output is one **Point** feature per stop (with `threat_band`, `dwell_min`,
`choke_point`, `fuel_available`), one **LineString** per leg (with
`distance_km`, `leg_threat`, `escort_required`, `over_policy`), and a single
whole-route LineString for styling the track. Coordinates use GeoJSON
`[lon, lat]` order.

## Route-risk analysis & alternate-route comparison — `convoy-or-risk`

The base scan answers a binary "does this one route pass policy?" question. The
**`convoy-or-risk`** command answers the comparative, quantitative question a
route-selection officer actually has: *of these candidate routes, which is least
dangerous, and where is the danger concentrated?*

It scores each route by **exposure** — threat-weighted time on route
(`leg_threat × (transit_min + dwell_min)`, summed) — because the dominant convoy
threat (the complex ambush / IED kill-zone) is driven by **how long** the convoy
spends in a threat band, not just the **peak** threat. Two routes with the same
peak threat can differ greatly in real risk. The base policy check is blind to
that; exposure-minutes are not.

```bash
# Rank three candidate routes, recommend the safest, show where risk concentrates
convoy-or-risk demos/10-route-compare/alpha-direct \
               demos/10-route-compare/bravo-bypass \
               demos/10-route-compare/charlie-night --format markdown

# Single-route brief; model a slower planned pace
convoy-or-risk demos/05-high-threat-corridor/ --speed 25

# Machine-readable comparison for a downstream tool
convoy-or-risk demos/10-route-compare/* --format json --out brief.json
```

Each route gets a **risk index** (0–100), a **band** (`low`/`elevated`/`high`/
`severe`), flagged **kill-zones** (choke + threat + dwell), an **over-policy** leg
count, and concrete defensive **recommendations** (escort, reroute, dwell
reduction, refuel). The ranking prefers (1) within-policy, then (2) lowest
exposure, then (3) shortest time on route — and will recommend a *longer* route
when it buys you out of a kill-zone.

> This is **decision support for a human route choice** — strictly defensive /
> force-protection. It does **not** target, cue, engage, or task any asset.

Full write-up, threat model, and worked example:
**[`docs/ROUTE_RISK.md`](docs/ROUTE_RISK.md)** (includes a generated SVG diagram).

## Classification banner

All output is wrapped with an operator-supplied classification banner.
**Default**: `UNCLASSIFIED//FOR PUBLIC RELEASE`.

> ⚠️ This tool **does not** generate or validate the *content* of higher
> classifications. Operators on cleared systems supply real markings at runtime.
> See [`../shared/cognis_mil/classmark.py`](../../shared/cognis_mil/classmark.py).

## Compliance crosswalks (built in)

Every finding can carry references to:
- **NIST 800-53 Rev 5** controls (e.g. `AC-2(1)`)
- **DISA STIG** rule IDs (e.g. `V-242414`)
- **MITRE ATT&CK** technique IDs (e.g. `T1078`)
- **CCI** (Control Correlation Identifier)

These are emitted in JSON, SARIF, and the OSCAL skeleton.

## CI / RMF integration

```yaml
- name: convoy-or scan
  run: |
    pip install cognis-convoy-or
    convoy-or . --format=oscal --out=assessment-results.json --fail-on=high
- name: Upload to eMASS/Xacta
  run: cognis-rmf-package import assessment-results.json
```

## Part of the Cognis Digital military / IC ecosystem

12 repos. All MIT/Apache-2.0/GPL-3 (per upstream). Cognis additions are
Apache-2.0 unless stated otherwise.

See [the master index](../../MASTER-INDEX.md).

## Interoperability

`convoy-or` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `convoy-or`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.
