"""GeoJSON (RFC 7946) export for convoy-or plans.

convoy-or is the one tool in the suite whose findings are inherently
*geospatial* — every stop carries a lat/lon, every leg is a line on a map.
This module renders a convoy ``plan.json`` as an RFC 7946 ``FeatureCollection``
so the route can be dropped straight into QGIS, kepler.gl, Leaflet, geojson.io,
or an ATAK/CivTAK overlay for a route brief.

Output structure:
  * one **Point** Feature per stop — props: name, dwell_min, threat_score,
    fuel_available, choke_point, and a derived ``threat_band`` (low/med/high).
  * one **LineString** Feature per leg — props: from, to, distance_km,
    leg_threat (max of endpoints), and ``escort_required`` against policy.
  * a trailing **LineString** Feature ``route`` covering the whole path, so a
    map renders the convoy track as a single styled line.

Coordinates follow GeoJSON order: ``[lon, lat]`` (RFC 7946 §3.1.1).

Usage:
    convoy-or-map demos/03-djibouti-port-run/        # reads plan.json
    convoy-or-map plan.json --out route.geojson
    convoy-or-map mission/ | geojsonio
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ConvoyPlan, Stop, Vehicle, evaluate_plan, haversine_km


def _threat_band(t: float) -> str:
    return "high" if t >= 0.7 else "medium" if t >= 0.4 else "low"


def plan_to_geojson(plan: ConvoyPlan) -> dict:
    """Render a ConvoyPlan as an RFC 7946 FeatureCollection."""
    features: list[dict] = []

    # Point feature per stop.
    for i, s in enumerate(plan.stops):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
            "properties": {
                "kind": "stop",
                "seq": i,
                "name": s.name,
                "dwell_min": s.dwell_min,
                "threat_score": s.threat_score,
                "threat_band": _threat_band(s.threat_score),
                "fuel_available": s.fuel_available,
                "choke_point": s.choke_point,
            },
        })

    # LineString feature per leg.
    for i in range(len(plan.stops) - 1):
        a, b = plan.stops[i], plan.stops[i + 1]
        leg_threat = max(a.threat_score, b.threat_score)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[a.lon, a.lat], [b.lon, b.lat]],
            },
            "properties": {
                "kind": "leg",
                "from": a.name,
                "to": b.name,
                "distance_km": round(haversine_km(a, b), 1),
                "leg_threat": leg_threat,
                "threat_band": _threat_band(leg_threat),
                "escort_required": leg_threat >= plan.escort_required_above_threat,
                "over_policy": leg_threat > plan.max_threat_per_leg,
            },
        })

    # Whole-route LineString for single-line styling.
    if len(plan.stops) >= 2:
        ev = evaluate_plan(plan)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[s.lon, s.lat] for s in plan.stops],
            },
            "properties": {
                "kind": "route",
                "total_km": ev["total_km"],
                "total_dwell_min": ev["total_dwell_min"],
                "max_threat_per_leg": ev["max_threat_per_leg"],
                "needs_refuel": ev["needs_refuel"],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        # Non-normative metadata; ignored by strict RFC 7946 readers.
        "properties": {"generator": "convoy-or", "schema": "rfc7946"},
    }


def _load_plan(target: str) -> ConvoyPlan:
    p = Path(target)
    plan_file = p / "plan.json" if p.is_dir() else p
    d = json.loads(plan_file.read_text(encoding="utf-8"))
    return ConvoyPlan(
        stops=[Stop(**s) for s in d["stops"]],
        vehicles=[Vehicle(**v) for v in d.get("vehicles", [])],
        escort_required_above_threat=d.get("escort_required_above_threat", 0.5),
        max_threat_per_leg=d.get("max_threat_per_leg", 0.7),
    )


def map_main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="convoy-or-map",
        description="Render a convoy-or plan as RFC 7946 GeoJSON for mapping tools.",
    )
    p.add_argument("target", nargs="?", default=".",
                   help="plan.json or a directory containing it (default: .)")
    p.add_argument("--out", help="write GeoJSON to this file (default: stdout)")
    a = p.parse_args(argv)
    try:
        plan = _load_plan(a.target)
    except FileNotFoundError:
        print(f"no plan.json at {a.target}", file=sys.stderr)
        return 1
    out = json.dumps(plan_to_geojson(plan), indent=2)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print(f"Wrote {a.out}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(map_main())
