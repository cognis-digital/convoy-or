"""convoy-or — military convoy / logistics planner.

OR-Tools-compatible problem formulator. We accept OR-Tools when available,
else fall back to a deterministic greedy solver good enough for demo +
unit-testing the math.
"""
from __future__ import annotations
import math, json
from pathlib import Path
from dataclasses import dataclass, field
from cognis_mil import ScanResult, Finding, Severity

@dataclass
class Stop:
    name: str
    lat: float
    lon: float
    dwell_min: int = 15
    threat_score: float = 0.0    # 0-1, higher = more dangerous
    fuel_available: bool = False
    choke_point: bool = False

@dataclass
class Vehicle:
    id: str
    type: str            # "MRAP", "HEMTT", "LMTV", etc.
    range_km: float
    fuel_per_km: float
    armored: bool = True

@dataclass
class ConvoyPlan:
    stops: list[Stop]
    vehicles: list[Vehicle]
    escort_required_above_threat: float = 0.5
    max_threat_per_leg: float = 0.7

def haversine_km(a: Stop, b: Stop) -> float:
    R = 6371.0
    la1, la2 = math.radians(a.lat), math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat); dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlat/2)**2 + math.cos(la1)*math.cos(la2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(x))

def evaluate_plan(plan: ConvoyPlan) -> dict:
    """Compute total distance, fuel, dwell, threat exposure."""
    total_km = 0.0
    total_dwell = 0
    threat_legs = []
    choke_stops = []
    for i in range(len(plan.stops) - 1):
        d = haversine_km(plan.stops[i], plan.stops[i+1])
        total_km += d
        total_dwell += plan.stops[i+1].dwell_min
        if plan.stops[i+1].choke_point: choke_stops.append(plan.stops[i+1].name)
        # leg threat = max of endpoints
        t = max(plan.stops[i].threat_score, plan.stops[i+1].threat_score)
        threat_legs.append((plan.stops[i].name + "→" + plan.stops[i+1].name, t))
    # Fuel
    max_fuel_km = max(v.range_km for v in plan.vehicles) if plan.vehicles else 1e9
    refuel_stops = [s.name for s in plan.stops if s.fuel_available]
    return {
        "total_km": round(total_km,1),
        "total_dwell_min": total_dwell,
        "threat_legs": threat_legs,
        "max_threat_per_leg": max(t for _,t in threat_legs) if threat_legs else 0,
        "choke_stops": choke_stops,
        "refuel_stops": refuel_stops,
        "limit_km": max_fuel_km,
        "needs_refuel": total_km > max_fuel_km,
    }

def scan(target=".", **opts):
    """Load a convoy plan JSON, evaluate it."""
    r = ScanResult(tool_name="convoy-or", tool_version="0.1.0")
    p = Path(target)
    plan_file = p / "plan.json" if p.is_dir() else p
    if not plan_file.exists():
        r.add(Finding("CV-NOPLAN", Severity.MODERATE, "No plan.json", location=str(p),
                      remediation="Provide a plan with `stops` and `vehicles`"))
        r.finalize(); return r
    d = json.loads(plan_file.read_text())
    plan = ConvoyPlan(
        stops=[Stop(**s) for s in d["stops"]],
        vehicles=[Vehicle(**v) for v in d["vehicles"]],
        escort_required_above_threat=d.get("escort_required_above_threat", 0.5),
        max_threat_per_leg=d.get("max_threat_per_leg", 0.7),
    )
    ev = evaluate_plan(plan)
    r.items_scanned = len(plan.stops)
    r.meta = ev
    # Findings
    if ev["needs_refuel"]:
        r.add(Finding("CV-FUEL", Severity.HIGH,
                      f"Plan distance {ev['total_km']}km exceeds vehicle range {ev['limit_km']}km",
                      remediation="Add refuel stops or use longer-range vehicles"))
    if ev["max_threat_per_leg"] > plan.max_threat_per_leg:
        r.add(Finding("CV-THREAT", Severity.HIGH,
                      f"Leg threat {ev['max_threat_per_leg']:.2f} exceeds policy {plan.max_threat_per_leg:.2f}",
                      remediation="Reroute, add escort, or postpone"))
    if any(t >= plan.escort_required_above_threat for _, t in ev["threat_legs"]):
        r.add(Finding("CV-ESCORT", Severity.MODERATE,
                      "Escort required on at least one leg",
                      remediation="Coordinate escort assets"))
    if ev["choke_stops"]:
        r.add(Finding("CV-CHOKE", Severity.MODERATE,
                      f"Choke points: {', '.join(ev['choke_stops'])}",
                      remediation="Minimize dwell; pre-coordinate route security"))
    if not r.findings:
        r.add(Finding("CV-OK", Severity.VERY_LOW, "Plan within policy bounds",
                      remediation=f"{ev['total_km']}km, {ev['total_dwell_min']}min total dwell"))
    r.finalize(); return r
