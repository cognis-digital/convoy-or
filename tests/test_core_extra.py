"""Extra coverage for convoy_or.core beyond the smoke tests."""
from pathlib import Path

import pytest

from convoy_or.core import (
    ConvoyPlan, Stop, Vehicle, evaluate_plan, haversine_km, scan,
)

D = Path(__file__).parent.parent / "demos"


def test_haversine_zero():
    a = Stop("a", 10.0, 20.0)
    assert haversine_km(a, a) == pytest.approx(0.0, abs=1e-6)


def test_haversine_symmetric():
    a = Stop("a", 34.0, -117.0)
    b = Stop("b", 35.0, -118.0)
    assert haversine_km(a, b) == pytest.approx(haversine_km(b, a))


def test_haversine_known_distance():
    # 1 degree of latitude ~ 111 km.
    a = Stop("a", 0.0, 0.0)
    b = Stop("b", 1.0, 0.0)
    assert haversine_km(a, b) == pytest.approx(111.0, abs=1.0)


def test_evaluate_total_km_accumulates():
    stops = [Stop("a", 0, 0), Stop("b", 0, 1), Stop("c", 0, 2)]
    ev = evaluate_plan(ConvoyPlan(stops=stops, vehicles=[Vehicle("v", "T", 1e6, 0.1)]))
    assert ev["total_km"] > 0


def test_evaluate_needs_refuel_true():
    stops = [Stop("a", 0, 0), Stop("b", 0, 5)]
    ev = evaluate_plan(ConvoyPlan(stops=stops, vehicles=[Vehicle("v", "T", 10, 0.1)]))
    assert ev["needs_refuel"] is True


def test_evaluate_needs_refuel_false():
    stops = [Stop("a", 0, 0), Stop("b", 0, 0.1)]
    ev = evaluate_plan(ConvoyPlan(stops=stops, vehicles=[Vehicle("v", "T", 1e6, 0.1)]))
    assert ev["needs_refuel"] is False


def test_evaluate_refuel_stops_listed():
    stops = [Stop("a", 0, 0, fuel_available=True),
             Stop("b", 0, 1, fuel_available=False),
             Stop("c", 0, 2, fuel_available=True)]
    ev = evaluate_plan(ConvoyPlan(stops=stops, vehicles=[Vehicle("v", "T", 1e6, 0.1)]))
    assert set(ev["refuel_stops"]) == {"a", "c"}


def test_evaluate_choke_stops_listed():
    stops = [Stop("a", 0, 0),
             Stop("b", 0, 1, choke_point=True),
             Stop("c", 0, 2)]
    ev = evaluate_plan(ConvoyPlan(stops=stops, vehicles=[Vehicle("v", "T", 1e6, 0.1)]))
    assert ev["choke_stops"] == ["b"]


def test_evaluate_no_vehicles_defaults_huge_range():
    stops = [Stop("a", 0, 0), Stop("b", 0, 100)]
    ev = evaluate_plan(ConvoyPlan(stops=stops, vehicles=[]))
    assert ev["needs_refuel"] is False  # huge default range


def test_scan_noplan_dir(tmp_path):
    r = scan(str(tmp_path))
    assert any(f.id == "CV-NOPLAN" for f in r.findings)


def test_scan_ok_baseline():
    r = scan(str(D / "03-djibouti-port-run"))
    assert any(f.id == "CV-OK" for f in r.findings)


def test_scan_fuel_finding():
    r = scan(str(D / "02-fuel-shortfall"))
    assert any(f.id == "CV-FUEL" for f in r.findings)


def test_scan_sets_meta():
    r = scan(str(D / "01-mixed"))
    assert "total_km" in r.meta
    assert r.items_scanned == 4


def test_scan_composite_score_finalised():
    r = scan(str(D / "09-max-risk-corridor"))
    assert r.composite_score > 0
    assert r.risk_level in {"Very Low", "Low", "Moderate", "High", "Very High"}


def test_stop_defaults():
    s = Stop("x", 1.0, 2.0)
    assert s.dwell_min == 15
    assert s.threat_score == 0.0
    assert s.fuel_available is False
    assert s.choke_point is False


def test_vehicle_defaults_armored():
    v = Vehicle("id", "MRAP", 100, 0.5)
    assert v.armored is True
