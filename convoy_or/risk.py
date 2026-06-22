"""convoy-or risk — quantitative route-risk analysis & alternate-route comparison.

The base ``convoy-or`` scan answers a *binary* question: does a single plan pass
policy (fuel / max-threat / escort / choke)?  That is necessary but not
sufficient for a route brief.  A route-selection officer needs to answer a
*comparative, quantitative* question:

    "Of these N candidate routes, which one exposes the convoy to the least
     risk, and *where* on the route is the risk concentrated?"

This module is the decision-support layer that answers that.  It is strictly
**defensive / force-protection / route-selection**: it scores and ranks routes
the planner already drew, surfaces where exposure concentrates, and recommends
mitigations (escort, reroute, dwell reduction).  It does **not** target,
engage, or task any asset — it informs a human route decision.

Threat model it addresses
-------------------------
The dominant kinetic threat to ground convoys is the *complex ambush / IED
kill-zone*: an attacker pre-positions on a segment where the convoy is forced
to slow (a choke point, defile, bridge, or built-up area) and where dwell or
low speed maximises the window in which the convoy is exposed.  Two routes can
share the same *peak* threat score yet differ enormously in real risk because
one spends ninety seconds in the kill-zone and the other spends twenty minutes.
Peak-threat policy checks are blind to this; **exposure-minutes** are not.

Core metric: exposure
---------------------
For each leg we estimate the time the convoy spends on it (distance / planned
speed) plus the dwell at the downstream stop, and weight it by the leg threat:

    leg_exposure  = leg_threat * (transit_min + downstream_dwell_min)

The route's **exposure score** is the sum of leg exposures.  We also report a
0-100 normalised ``risk_index`` (a bounded, comparable figure) and a
*choke-vulnerability* roll-up that flags the segments where threat AND dwell
AND a choke flag coincide — the textbook kill-zone signature.

Everything is deterministic, offline, and unit-tested.  No network, no targeting.

Usage
-----
    convoy-or-risk demos/05-high-threat-corridor/         # single route brief
    convoy-or-risk routeA/ routeB/ routeC/ --format markdown   # compare & rank
    convoy-or-risk a.json b.json --speed 40 --format json --out brief.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .core import ConvoyPlan, Stop, Vehicle, evaluate_plan, haversine_km

# Default planning ground speed (km/h) when a plan does not specify one.
# 40 km/h is a conservative tactical convoy cruise; built-up / choke segments
# move slower, which we model with the choke-speed factor below.
DEFAULT_SPEED_KMH = 40.0

# A choke segment is assumed to move at this fraction of cruise speed, which
# *increases* time-in-segment and therefore exposure — the whole point of a
# kill-zone is that you cannot transit it quickly.
CHOKE_SPEED_FACTOR = 0.5

# Normalisation ceiling for the 0-100 risk index. Exposure beyond this saturates
# at 100. Chosen so a long, high-threat, choke-laden route lands near the top of
# the band while a permissive line-haul stays low. Tunable per theatre.
RISK_INDEX_CEILING = 600.0


def _band(idx: float) -> str:
    """Map a 0-100 risk index to a four-tier band for at-a-glance triage."""
    if idx >= 70:
        return "severe"
    if idx >= 40:
        return "high"
    if idx >= 15:
        return "elevated"
    return "low"


@dataclass
class LegRisk:
    frm: str
    to: str
    distance_km: float
    threat: float
    transit_min: float
    dwell_min: int
    exposure: float
    choke: bool
    escort_required: bool
    over_policy: bool

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        for k in ("distance_km", "transit_min", "exposure"):
            d[k] = round(d[k], 2)
        d["threat"] = round(d["threat"], 3)
        return d


@dataclass
class RouteRisk:
    name: str
    total_km: float
    total_transit_min: float
    total_dwell_min: int
    time_on_route_min: float
    exposure_score: float
    risk_index: float
    band: str
    peak_threat: float
    legs: list[LegRisk] = field(default_factory=list)
    choke_kill_zones: list[str] = field(default_factory=list)
    needs_refuel: bool = False
    over_policy_legs: int = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_km": round(self.total_km, 1),
            "total_transit_min": round(self.total_transit_min, 1),
            "total_dwell_min": self.total_dwell_min,
            "time_on_route_min": round(self.time_on_route_min, 1),
            "exposure_score": round(self.exposure_score, 2),
            "risk_index": round(self.risk_index, 1),
            "band": self.band,
            "peak_threat": round(self.peak_threat, 3),
            "needs_refuel": self.needs_refuel,
            "over_policy_legs": self.over_policy_legs,
            "choke_kill_zones": self.choke_kill_zones,
            "legs": [l.to_dict() for l in self.legs],
            "recommendations": self.recommendations,
        }


def _transit_min(distance_km: float, speed_kmh: float, choke: bool) -> float:
    """Estimate minutes to transit a leg, slowing through choke segments."""
    effective = speed_kmh * (CHOKE_SPEED_FACTOR if choke else 1.0)
    if effective <= 0:
        effective = DEFAULT_SPEED_KMH
    return (distance_km / effective) * 60.0


def analyze_route(plan: ConvoyPlan, name: str = "route",
                  speed_kmh: float = DEFAULT_SPEED_KMH) -> RouteRisk:
    """Produce a quantitative risk profile for a single convoy plan.

    The leg threat is the max of its two endpoints (matching core's convention);
    a leg is treated as a choke segment if either endpoint is flagged
    ``choke_point``. Exposure is threat-weighted time-in-segment.
    """
    legs: list[LegRisk] = []
    total_km = 0.0
    total_transit = 0.0
    total_dwell = 0
    exposure = 0.0
    peak = 0.0
    kill_zones: list[str] = []
    over_policy = 0

    for i in range(len(plan.stops) - 1):
        a, b = plan.stops[i], plan.stops[i + 1]
        d = haversine_km(a, b)
        threat = max(a.threat_score, b.threat_score)
        choke = bool(a.choke_point or b.choke_point)
        transit = _transit_min(d, speed_kmh, choke)
        dwell = b.dwell_min
        leg_exposure = threat * (transit + dwell)

        is_over = threat > plan.max_threat_per_leg
        escort = threat >= plan.escort_required_above_threat
        if is_over:
            over_policy += 1
        # Kill-zone signature: a choke segment that is also a real threat and
        # where the convoy is made to dwell. This is where complex ambushes live.
        if choke and threat >= 0.5 and (dwell > 0 or threat >= 0.7):
            kill_zones.append(f"{a.name}->{b.name}")

        legs.append(LegRisk(
            frm=a.name, to=b.name, distance_km=d, threat=threat,
            transit_min=transit, dwell_min=dwell, exposure=leg_exposure,
            choke=choke, escort_required=escort, over_policy=is_over,
        ))
        total_km += d
        total_transit += transit
        total_dwell += dwell
        exposure += leg_exposure
        peak = max(peak, threat)

    time_on_route = total_transit + total_dwell
    risk_index = min(100.0, (exposure / RISK_INDEX_CEILING) * 100.0)

    ev = evaluate_plan(plan) if plan.stops else {"needs_refuel": False}

    rr = RouteRisk(
        name=name,
        total_km=total_km,
        total_transit_min=total_transit,
        total_dwell_min=total_dwell,
        time_on_route_min=time_on_route,
        exposure_score=exposure,
        risk_index=risk_index,
        band=_band(risk_index),
        peak_threat=peak,
        legs=legs,
        choke_kill_zones=kill_zones,
        needs_refuel=bool(ev.get("needs_refuel")),
        over_policy_legs=over_policy,
    )
    rr.recommendations = _recommend(rr, plan)
    return rr


def _recommend(rr: RouteRisk, plan: ConvoyPlan) -> list[str]:
    """Generate concrete, defensive route-brief recommendations."""
    recs: list[str] = []
    if rr.over_policy_legs:
        recs.append(
            f"{rr.over_policy_legs} leg(s) exceed the max-threat policy "
            f"({plan.max_threat_per_leg:.2f}); reroute or postpone, or obtain a "
            f"risk-acceptance decision from the approving authority before movement.")
    if rr.choke_kill_zones:
        recs.append(
            "Potential ambush/IED kill-zone(s): "
            + ", ".join(rr.choke_kill_zones)
            + ". Minimise dwell, vary timing, pre-clear/route-recon, and "
              "pre-coordinate overwatch or QRF for these segments.")
    escort_legs = [f"{l.frm}->{l.to}" for l in rr.legs if l.escort_required]
    if escort_legs:
        recs.append("Escort required on: " + ", ".join(escort_legs) + ".")
    if rr.needs_refuel:
        recs.append("Planned distance exceeds vehicle range; insert a refuel "
                    "stop or assign longer-range vehicles.")
    high_dwell = [l for l in rr.legs if l.dwell_min >= 10 and l.threat >= 0.5]
    if high_dwell:
        worst = max(high_dwell, key=lambda l: l.threat * l.dwell_min)
        recs.append(
            f"Reduce dwell at {worst.to} ({worst.dwell_min} min at threat "
            f"{worst.threat:.2f}) — dwell in a threat band compounds exposure.")
    if not recs:
        recs.append("Within policy bounds. Maintain standard force-protection posture.")
    return recs


def compare_routes(routes: list[RouteRisk]) -> dict:
    """Rank candidate routes lowest-exposure-first and pick a recommendation.

    Ranking key prioritises (1) staying within max-threat policy, then
    (2) lowest exposure score, then (3) shortest time on route. The first route
    after sorting is the recommended movement option.
    """
    ranked = sorted(
        routes,
        key=lambda r: (r.over_policy_legs, r.exposure_score, r.time_on_route_min),
    )
    best = ranked[0] if ranked else None
    out = {
        "candidates": len(routes),
        "ranking": [r.name for r in ranked],
        "recommended": best.name if best else None,
        "routes": {r.name: r.to_dict() for r in routes},
    }
    if best and len(ranked) > 1:
        runner = ranked[1]
        delta = runner.exposure_score - best.exposure_score
        out["margin"] = round(delta, 2)
        out["rationale"] = (
            f"'{best.name}' is recommended: exposure {best.exposure_score:.1f} "
            f"vs next-best '{runner.name}' {runner.exposure_score:.1f} "
            f"(delta {delta:.1f}), {best.over_policy_legs} over-policy leg(s).")
    elif best:
        out["rationale"] = (
            f"'{best.name}' is the only candidate: exposure "
            f"{best.exposure_score:.1f}, {best.over_policy_legs} over-policy leg(s).")
    return out


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------

def to_markdown(comparison: dict) -> str:
    out = ["# Convoy route-risk brief", ""]
    out.append("> UNCLASSIFIED//FOR PUBLIC RELEASE — decision support only; "
               "not a targeting or tasking product.")
    out.append("")
    out.append(f"**Candidates:** {comparison['candidates']}  ")
    out.append(f"**Recommended route:** `{comparison.get('recommended')}`  ")
    if comparison.get("rationale"):
        out.append(f"**Rationale:** {comparison['rationale']}")
    out.append("")
    out.append("## Ranking (lowest risk first)")
    out.append("")
    out.append("| Rank | Route | Risk index | Band | Exposure | Time (min) | Dist (km) | Over-policy | Kill-zones |")
    out.append("|------|-------|-----------|------|----------|-----------|-----------|-------------|------------|")
    for rank, name in enumerate(comparison["ranking"], 1):
        r = comparison["routes"][name]
        out.append(
            f"| {rank} | `{name}` | {r['risk_index']} | {r['band']} | "
            f"{r['exposure_score']} | {r['time_on_route_min']} | {r['total_km']} | "
            f"{r['over_policy_legs']} | {len(r['choke_kill_zones'])} |")
    out.append("")
    for name in comparison["ranking"]:
        r = comparison["routes"][name]
        out.append(f"## Route `{name}` — risk index {r['risk_index']}/100 ({r['band']})")
        out.append("")
        out.append(f"- Distance: {r['total_km']} km, time on route: {r['time_on_route_min']} min "
                   f"({r['total_transit_min']} transit + {r['total_dwell_min']} dwell)")
        out.append(f"- Peak leg threat: {r['peak_threat']}, exposure score: {r['exposure_score']}")
        if r["choke_kill_zones"]:
            out.append(f"- **Potential kill-zones:** {', '.join(r['choke_kill_zones'])}")
        out.append("")
        out.append("| Leg | Threat | Choke | Transit (min) | Dwell | Exposure | Escort | Over-policy |")
        out.append("|-----|--------|-------|---------------|-------|----------|--------|-------------|")
        for l in r["legs"]:
            out.append(
                f"| {l['frm']}->{l['to']} | {l['threat']} | "
                f"{'yes' if l['choke'] else ''} | {l['transit_min']} | {l['dwell_min']} | "
                f"{l['exposure']} | {'yes' if l['escort_required'] else ''} | "
                f"{'yes' if l['over_policy'] else ''} |")
        out.append("")
        out.append("**Recommendations:**")
        for rec in r["recommendations"]:
            out.append(f"- {rec}")
        out.append("")
    return "\n".join(out)


def to_console(comparison: dict) -> str:
    L = ["=" * 72,
         "  CONVOY ROUTE-RISK BRIEF  (UNCLASSIFIED//FOR PUBLIC RELEASE)",
         "  decision support only - not a targeting or tasking product",
         "=" * 72,
         f"  Candidates: {comparison['candidates']}   "
         f"Recommended: {comparison.get('recommended')}"]
    if comparison.get("rationale"):
        L.append(f"  {comparison['rationale']}")
    L.append("-" * 72)
    for rank, name in enumerate(comparison["ranking"], 1):
        r = comparison["routes"][name]
        L.append(f"  #{rank}  {name:<22} idx {r['risk_index']:>5}/100 "
                 f"[{r['band']:<8}] exp {r['exposure_score']:>7} "
                 f"{r['total_km']:>6}km")
        if r["choke_kill_zones"]:
            L.append(f"        kill-zones: {', '.join(r['choke_kill_zones'])}")
    L.append("=" * 72)
    return "\n".join(L)


# ----------------------------------------------------------------------------
# Loading / CLI
# ----------------------------------------------------------------------------

def load_plan(target: str) -> ConvoyPlan:
    p = Path(target)
    plan_file = p / "plan.json" if p.is_dir() else p
    d = json.loads(plan_file.read_text(encoding="utf-8"))
    return ConvoyPlan(
        stops=[Stop(**s) for s in d["stops"]],
        vehicles=[Vehicle(**v) for v in d.get("vehicles", [])],
        escort_required_above_threat=d.get("escort_required_above_threat", 0.5),
        max_threat_per_leg=d.get("max_threat_per_leg", 0.7),
    )


def _route_name(target: str) -> str:
    p = Path(target)
    return p.name if p.is_dir() else (p.parent.name + "/" + p.stem if p.parent.name else p.stem)


def risk_main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="convoy-or-risk",
        description="Quantitative convoy route-risk analysis & alternate-route "
                    "comparison (defensive / force-protection decision support).")
    p.add_argument("targets", nargs="*", default=["."],
                   help="one or more plan.json files or directories (default: .)")
    p.add_argument("--speed", type=float, default=DEFAULT_SPEED_KMH,
                   help=f"planning ground speed km/h (default {DEFAULT_SPEED_KMH})")
    p.add_argument("--format", choices=["console", "json", "markdown"],
                   default="console")
    p.add_argument("--out", help="write output to this file (default: stdout)")
    a = p.parse_args(argv)

    targets = a.targets or ["."]
    routes: list[RouteRisk] = []
    for t in targets:
        try:
            plan = load_plan(t)
        except FileNotFoundError:
            print(f"no plan.json at {t}", file=sys.stderr)
            return 1
        except (KeyError, json.JSONDecodeError) as exc:
            print(f"invalid plan at {t}: {exc}", file=sys.stderr)
            return 1
        routes.append(analyze_route(plan, name=_route_name(t), speed_kmh=a.speed))

    comparison = compare_routes(routes)

    if a.format == "json":
        out = json.dumps(comparison, indent=2)
    elif a.format == "markdown":
        out = to_markdown(comparison)
    else:
        out = to_console(comparison)

    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print(f"Wrote {a.out}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(risk_main())
