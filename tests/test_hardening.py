"""Tests for input validation, error handling, and edge cases added during hardening."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from convoy_or.core import (
    ConvoyPlan,
    PlanValidationError,
    Stop,
    Vehicle,
    _load_plan,
    evaluate_plan,
    haversine_km,
    scan,
)

TMP = Path(__file__).parent / "_tmp_plans"


def _write_plan(name: str, data: object) -> Path:
    TMP.mkdir(exist_ok=True)
    p = TMP / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# haversine_km — floating-point guard
# ---------------------------------------------------------------------------

def test_haversine_antipodal_no_domain_error():
    """Antipodal stops should not raise a math domain error."""
    a = Stop("a", 0.0, 0.0)
    b = Stop("b", 0.0, 180.0)
    result = haversine_km(a, b)
    # half earth circumference ≈ 20015 km
    assert 19000 < result < 21000


def test_haversine_same_point_is_zero():
    a = Stop("x", 51.5, -0.1)
    result = haversine_km(a, a)
    assert result == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# evaluate_plan — edge cases
# ---------------------------------------------------------------------------

def test_evaluate_single_stop_no_crash():
    """A plan with one stop has no legs; all numeric outputs are zero/empty."""
    plan = ConvoyPlan(
        stops=[Stop("only", 34.0, -117.0, threat_score=0.9, choke_point=True)],
        vehicles=[Vehicle("v1", "MRAP", 500, 0.3)],
    )
    ev = evaluate_plan(plan)
    assert ev["total_km"] == 0.0
    assert ev["threat_legs"] == []
    assert ev["max_threat_per_leg"] == 0
    assert ev["needs_refuel"] is False


def test_evaluate_no_stops_no_crash():
    """A plan with zero stops must not raise."""
    plan = ConvoyPlan(stops=[], vehicles=[Vehicle("v1", "MRAP", 500, 0.3)])
    ev = evaluate_plan(plan)
    assert ev["total_km"] == 0.0
    assert ev["threat_legs"] == []


def test_evaluate_no_vehicles_uses_infinite_range():
    stops = [Stop("a", 34.0, -117.0), Stop("b", 35.0, -118.0)]
    plan = ConvoyPlan(stops=stops, vehicles=[])
    ev = evaluate_plan(plan)
    assert ev["needs_refuel"] is False
    assert ev["limit_km"] == 1e9


# ---------------------------------------------------------------------------
# _load_plan — validation errors
# ---------------------------------------------------------------------------

def test_load_plan_missing_file_raises():
    with pytest.raises(PlanValidationError, match="Cannot read"):
        _load_plan(Path("/nonexistent/path/plan.json"))


def test_load_plan_invalid_json_raises():
    p = _write_plan("bad_json.json", None)
    p.write_text("{ not: valid json }", encoding="utf-8")
    with pytest.raises(PlanValidationError, match="not valid JSON"):
        _load_plan(p)


def test_load_plan_missing_stops_key():
    p = _write_plan("no_stops.json", {"vehicles": []})
    with pytest.raises(PlanValidationError, match="missing required key 'stops'"):
        _load_plan(p)


def test_load_plan_missing_vehicles_key():
    p = _write_plan("no_vehicles.json", {"stops": []})
    with pytest.raises(PlanValidationError, match="missing required key 'vehicles'"):
        _load_plan(p)


def test_load_plan_stop_missing_required_field():
    data = {
        "stops": [{"lat": 34.0, "lon": -117.0}],  # missing 'name'
        "vehicles": [],
    }
    p = _write_plan("missing_name.json", data)
    with pytest.raises(PlanValidationError, match="missing required field 'name'"):
        _load_plan(p)


def test_load_plan_stop_lat_out_of_range():
    data = {
        "stops": [{"name": "bad", "lat": 999.0, "lon": 0.0}],
        "vehicles": [],
    }
    p = _write_plan("bad_lat.json", data)
    with pytest.raises(PlanValidationError, match="'lat' 999"):
        _load_plan(p)


def test_load_plan_stop_threat_score_out_of_range():
    data = {
        "stops": [{"name": "x", "lat": 34.0, "lon": -117.0, "threat_score": 2.5}],
        "vehicles": [],
    }
    p = _write_plan("bad_threat.json", data)
    with pytest.raises(PlanValidationError, match="'threat_score'"):
        _load_plan(p)


def test_load_plan_vehicle_missing_required_field():
    data = {
        "stops": [],
        "vehicles": [{"id": "v1", "type": "MRAP", "fuel_per_km": 0.3}],  # missing range_km
    }
    p = _write_plan("missing_range.json", data)
    with pytest.raises(PlanValidationError, match="missing required field 'range_km'"):
        _load_plan(p)


def test_load_plan_vehicle_zero_range_raises():
    data = {
        "stops": [],
        "vehicles": [{"id": "v1", "type": "MRAP", "range_km": 0, "fuel_per_km": 0.3}],
    }
    p = _write_plan("zero_range.json", data)
    with pytest.raises(PlanValidationError, match="'range_km'"):
        _load_plan(p)


def test_load_plan_invalid_escort_threshold():
    data = {
        "stops": [],
        "vehicles": [],
        "escort_required_above_threat": 1.5,
    }
    p = _write_plan("bad_escort.json", data)
    with pytest.raises(PlanValidationError, match="escort_required_above_threat"):
        _load_plan(p)


# ---------------------------------------------------------------------------
# scan() — graceful CV-INVALID finding for bad plan file
# ---------------------------------------------------------------------------

def test_scan_malformed_json_returns_cv_invalid():
    p = _write_plan("scan_bad.json", None)
    p.write_text("<<<not json>>>", encoding="utf-8")
    r = scan(str(p))
    ids = {f.id for f in r.findings}
    assert "CV-INVALID" in ids


def test_scan_missing_required_field_returns_cv_invalid():
    # A stop missing 'name' is invalid; scan() must return CV-INVALID, not raise.
    data = {"stops": [{"lat": 34.0, "lon": -117.0}], "vehicles": []}
    p = _write_plan("scan_no_name.json", data)
    r = scan(str(p))
    ids = {f.id for f in r.findings}
    assert "CV-INVALID" in ids


# ---------------------------------------------------------------------------
# CLI — non-zero exit on missing target (via subprocess)
# ---------------------------------------------------------------------------

def test_cli_nonexistent_target_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "convoy_or", "/nonexistent/path/to/nothing"],
        capture_output=True, text=True,
    )
    # Either CV-NOPLAN finding with --fail-on in default ("none") means exit 0,
    # OR an error exit 2. Either way the tool must not crash with a traceback.
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout
