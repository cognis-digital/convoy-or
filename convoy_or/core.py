"""convoy-or — military convoy / logistics planner.

OR-Tools-compatible problem formulator. We accept OR-Tools when available,
else fall back to a deterministic greedy solver good enough for demo +
unit-testing the math.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from dataclasses import dataclass
from cognis_mil import ScanResult, Finding, Severity

_REQUIRED_STOP_FIELDS = ("name", "lat", "lon")
_REQUIRED_VEHICLE_FIELDS = ("id", "type", "range_km", "fuel_per_km")


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


class PlanValidationError(ValueError):
    """Raised when a plan.json fails structural or range validation."""


def _validate_stop_dict(idx: int, s: dict) -> None:
    for field in _REQUIRED_STOP_FIELDS:
        if field not in s:
            raise PlanValidationError(f"Stop[{idx}] missing required field '{field}'")
    lat, lon = s["lat"], s["lon"]
    if not isinstance(lat, (int, float)):
        raise PlanValidationError(f"Stop[{idx}] 'lat' must be numeric, got {type(lat).__name__}")
    if not isinstance(lon, (int, float)):
        raise PlanValidationError(f"Stop[{idx}] 'lon' must be numeric, got {type(lon).__name__}")
    if not (-90.0 <= lat <= 90.0):
        raise PlanValidationError(f"Stop[{idx}] 'lat' {lat} out of range [-90, 90]")
    if not (-180.0 <= lon <= 180.0):
        raise PlanValidationError(f"Stop[{idx}] 'lon' {lon} out of range [-180, 180]")
    ts = s.get("threat_score", 0.0)
    if not isinstance(ts, (int, float)):
        raise PlanValidationError(f"Stop[{idx}] 'threat_score' must be numeric")
    if not (0.0 <= float(ts) <= 1.0):
        raise PlanValidationError(f"Stop[{idx}] 'threat_score' {ts} out of range [0, 1]")
    dwell = s.get("dwell_min", 15)
    if not isinstance(dwell, (int, float)) or float(dwell) < 0:
        raise PlanValidationError(f"Stop[{idx}] 'dwell_min' must be a non-negative number")


def _validate_vehicle_dict(idx: int, v: dict) -> None:
    for field in _REQUIRED_VEHICLE_FIELDS:
        if field not in v:
            raise PlanValidationError(f"Vehicle[{idx}] missing required field '{field}'")
    rng = v["range_km"]
    fpk = v["fuel_per_km"]
    if not isinstance(rng, (int, float)) or float(rng) <= 0:
        raise PlanValidationError(f"Vehicle[{idx}] 'range_km' must be a positive number, got {rng!r}")
    if not isinstance(fpk, (int, float)) or float(fpk) < 0:
        raise PlanValidationError(f"Vehicle[{idx}] 'fuel_per_km' must be a non-negative number, got {fpk!r}")


def haversine_km(a: Stop, b: Stop) -> float:
    R = 6371.0
    la1, la2 = math.radians(a.lat), math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlat/2)**2 + math.cos(la1)*math.cos(la2)*math.sin(dlon/2)**2
    # Clamp to [0, 1] to guard against floating-point rounding past the domain
    # boundary of asin (e.g. x = 1.0000000000000002 for antipodal points).
    return 2 * R * math.asin(math.sqrt(max(0.0, min(1.0, x))))

def evaluate_plan(plan: ConvoyPlan) -> dict:
    """Compute total distance, fuel, dwell, threat exposure."""
    if len(plan.stops) < 2:
        max_fuel_km = max(v.range_km for v in plan.vehicles) if plan.vehicles else 1e9
        return {
            "total_km": 0.0,
            "total_dwell_min": plan.stops[0].dwell_min if plan.stops else 0,
            "threat_legs": [],
            "max_threat_per_leg": 0,
            "choke_stops": [s.name for s in plan.stops if s.choke_point],
            "refuel_stops": [s.name for s in plan.stops if s.fuel_available],
            "limit_km": max_fuel_km,
            "needs_refuel": False,
        }
    total_km = 0.0
    total_dwell = 0
    threat_legs = []
    choke_stops = []
    for i in range(len(plan.stops) - 1):
        d = haversine_km(plan.stops[i], plan.stops[i+1])
        total_km += d
        total_dwell += plan.stops[i+1].dwell_min
        if plan.stops[i+1].choke_point:
            choke_stops.append(plan.stops[i+1].name)
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

def _load_plan(plan_file: Path) -> ConvoyPlan:
    """Parse and validate plan.json, raising PlanValidationError on bad input."""
    try:
        raw = plan_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlanValidationError(f"Cannot read plan file: {exc}") from exc

    try:
        d = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanValidationError(f"plan.json is not valid JSON: {exc}") from exc

    if not isinstance(d, dict):
        raise PlanValidationError("plan.json must be a JSON object")

    if "stops" not in d:
        raise PlanValidationError("plan.json missing required key 'stops'")
    if "vehicles" not in d:
        raise PlanValidationError("plan.json missing required key 'vehicles'")

    if not isinstance(d["stops"], list):
        raise PlanValidationError("'stops' must be a JSON array")
    if not isinstance(d["vehicles"], list):
        raise PlanValidationError("'vehicles' must be a JSON array")

    stops_raw = d["stops"]
    vehicles_raw = d["vehicles"]

    for idx, s in enumerate(stops_raw):
        if not isinstance(s, dict):
            raise PlanValidationError(f"stops[{idx}] must be a JSON object")
        _validate_stop_dict(idx, s)

    for idx, v in enumerate(vehicles_raw):
        if not isinstance(v, dict):
            raise PlanValidationError(f"vehicles[{idx}] must be a JSON object")
        _validate_vehicle_dict(idx, v)

    try:
        stops = [Stop(**s) for s in stops_raw]
    except TypeError as exc:
        raise PlanValidationError(f"Invalid stop field: {exc}") from exc

    try:
        vehicles = [Vehicle(**v) for v in vehicles_raw]
    except TypeError as exc:
        raise PlanValidationError(f"Invalid vehicle field: {exc}") from exc

    ert = d.get("escort_required_above_threat", 0.5)
    mtp = d.get("max_threat_per_leg", 0.7)
    if not isinstance(ert, (int, float)) or not (0.0 <= float(ert) <= 1.0):
        raise PlanValidationError(f"'escort_required_above_threat' must be in [0, 1], got {ert!r}")
    if not isinstance(mtp, (int, float)) or not (0.0 <= float(mtp) <= 1.0):
        raise PlanValidationError(f"'max_threat_per_leg' must be in [0, 1], got {mtp!r}")

    return ConvoyPlan(
        stops=stops,
        vehicles=vehicles,
        escort_required_above_threat=float(ert),
        max_threat_per_leg=float(mtp),
    )


def scan(target=".", **opts):
    """Load a convoy plan JSON, evaluate it."""
    r = ScanResult(tool_name="convoy-or", tool_version="0.1.0")
    p = Path(target)
    plan_file = p / "plan.json" if p.is_dir() else p
    if not plan_file.exists():
        r.add(Finding("CV-NOPLAN", Severity.MODERATE, "No plan.json", location=str(p),
                      remediation="Provide a plan with `stops` and `vehicles`"))
        r.finalize()
        return r

    try:
        plan = _load_plan(plan_file)
    except PlanValidationError as exc:
        r.add(Finding("CV-INVALID", Severity.HIGH, f"Plan file invalid: {exc}",
                      location=str(plan_file),
                      remediation="Fix the plan.json structure and field values"))
        r.finalize()
        return r

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
    r.finalize()
    return r
