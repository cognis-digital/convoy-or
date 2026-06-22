"""Tests for the route-risk analysis & alternate-route comparison engine.

All offline and deterministic. No network, no fixtures beyond the committed
demo plans and in-memory ConvoyPlan objects.
"""
from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

import pytest

from convoy_or.core import ConvoyPlan, Stop, Vehicle
from convoy_or import risk
from convoy_or.risk import (
    CHOKE_SPEED_FACTOR,
    DEFAULT_SPEED_KMH,
    RISK_INDEX_CEILING,
    LegRisk,
    RouteRisk,
    _band,
    _route_name,
    _transit_min,
    analyze_route,
    compare_routes,
    load_plan,
    risk_main,
    to_console,
    to_markdown,
)

D = Path(__file__).parent.parent / "demos"
RC = D / "10-route-compare"


# --------------------------------------------------------------------------
# Fixtures / builders
# --------------------------------------------------------------------------

def _plan(escort=0.5, ceiling=0.7):
    return ConvoyPlan(
        stops=[
            Stop("Start", 33.0, 44.0, dwell_min=0, threat_score=0.2),
            Stop("Mid", 33.2, 44.1, dwell_min=10, threat_score=0.55, choke_point=True),
            Stop("Hot", 33.4, 44.2, dwell_min=5, threat_score=0.8, choke_point=True),
            Stop("End", 33.6, 44.3, dwell_min=0, threat_score=0.25),
        ],
        vehicles=[Vehicle("v", "MRAP", 900, 0.6)],
        escort_required_above_threat=escort,
        max_threat_per_leg=ceiling,
    )


def _flat_plan():
    return ConvoyPlan(
        stops=[Stop("A", 0.0, 0.0, threat_score=0.1),
               Stop("B", 0.0, 1.0, threat_score=0.1)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)],
    )


# --------------------------------------------------------------------------
# _band
# --------------------------------------------------------------------------

@pytest.mark.parametrize("idx,expected", [
    (0, "low"), (5, "low"), (14.9, "low"),
    (15, "elevated"), (39.9, "elevated"),
    (40, "high"), (69.9, "high"),
    (70, "severe"), (100, "severe"),
])
def test_band_thresholds(idx, expected):
    assert _band(idx) == expected


def test_band_monotonic_order():
    order = ["low", "elevated", "high", "severe"]
    seen = [_band(x) for x in (0, 20, 50, 90)]
    assert seen == order


# --------------------------------------------------------------------------
# _transit_min
# --------------------------------------------------------------------------

def test_transit_basic():
    # 40 km at 40 km/h non-choke = 60 minutes
    assert _transit_min(40.0, 40.0, choke=False) == pytest.approx(60.0)


def test_transit_choke_is_slower():
    fast = _transit_min(40.0, 40.0, choke=False)
    slow = _transit_min(40.0, 40.0, choke=True)
    assert slow == pytest.approx(fast / CHOKE_SPEED_FACTOR)
    assert slow > fast


def test_transit_zero_distance():
    assert _transit_min(0.0, 40.0, choke=False) == 0.0


def test_transit_zero_speed_falls_back():
    # Must not divide by zero.
    val = _transit_min(40.0, 0.0, choke=False)
    assert val > 0 and math.isfinite(val)


def test_transit_negative_speed_falls_back():
    val = _transit_min(40.0, -10.0, choke=False)
    assert val > 0 and math.isfinite(val)


# --------------------------------------------------------------------------
# analyze_route — structure
# --------------------------------------------------------------------------

def test_analyze_returns_routerisk():
    assert isinstance(analyze_route(_plan()), RouteRisk)


def test_analyze_leg_count():
    rr = analyze_route(_plan())
    assert len(rr.legs) == 3  # 4 stops -> 3 legs


def test_analyze_leg_types():
    rr = analyze_route(_plan())
    assert all(isinstance(l, LegRisk) for l in rr.legs)


def test_analyze_name_propagates():
    assert analyze_route(_plan(), name="ALPHA").name == "ALPHA"


def test_analyze_default_name():
    assert analyze_route(_plan()).name == "route"


def test_analyze_peak_threat():
    rr = analyze_route(_plan())
    assert rr.peak_threat == pytest.approx(0.8)


def test_analyze_totals_positive():
    rr = analyze_route(_plan())
    assert rr.total_km > 0
    assert rr.total_transit_min > 0
    assert rr.exposure_score > 0


def test_analyze_total_dwell_sum():
    rr = analyze_route(_plan())
    # downstream dwell of legs: Mid(10)+Hot(5)+End(0) = 15
    assert rr.total_dwell_min == 15


def test_analyze_time_on_route_is_transit_plus_dwell():
    rr = analyze_route(_plan())
    assert rr.time_on_route_min == pytest.approx(rr.total_transit_min + rr.total_dwell_min)


def test_analyze_exposure_is_sum_of_legs():
    rr = analyze_route(_plan())
    assert rr.exposure_score == pytest.approx(sum(l.exposure for l in rr.legs))


def test_analyze_risk_index_bounded():
    rr = analyze_route(_plan())
    assert 0 <= rr.risk_index <= 100


def test_analyze_band_matches_index():
    rr = analyze_route(_plan())
    assert rr.band == _band(rr.risk_index)


# --------------------------------------------------------------------------
# analyze_route — exposure math
# --------------------------------------------------------------------------

def test_leg_exposure_formula():
    rr = analyze_route(_plan())
    for l in rr.legs:
        assert l.exposure == pytest.approx(l.threat * (l.transit_min + l.dwell_min))


def test_leg_threat_is_max_of_endpoints():
    rr = analyze_route(_plan())
    # Start(0.2)->Mid(0.55) leg threat = 0.55
    leg0 = rr.legs[0]
    assert leg0.threat == pytest.approx(0.55)


def test_choke_flag_when_either_endpoint_choke():
    rr = analyze_route(_plan())
    # Start->Mid: Mid is choke -> leg choke True
    assert rr.legs[0].choke is True
    # Mid->Hot: both choke
    assert rr.legs[1].choke is True
    # Hot->End: neither flagged choke at End, Hot is choke -> True
    assert rr.legs[2].choke is True


def test_higher_dwell_increases_exposure():
    base = analyze_route(_plan())
    p2 = _plan()
    p2.stops[1].dwell_min = 60  # much longer dwell at Mid
    more = analyze_route(p2)
    assert more.exposure_score > base.exposure_score


def test_risk_index_saturates_at_100():
    # Build an extreme route whose raw exposure far exceeds the ceiling.
    stops = [Stop(f"S{i}", 0.0, float(i), threat_score=1.0, choke_point=True, dwell_min=120)
             for i in range(8)]
    p = ConvoyPlan(stops=stops, vehicles=[Vehicle("v", "T", 1e6, 0.1)])
    rr = analyze_route(p)
    assert rr.exposure_score > RISK_INDEX_CEILING
    assert rr.risk_index == 100.0
    assert rr.band == "severe"


def test_speed_affects_transit_not_dwell():
    slow = analyze_route(_plan(), speed_kmh=20)
    fast = analyze_route(_plan(), speed_kmh=80)
    assert slow.total_transit_min > fast.total_transit_min
    assert slow.total_dwell_min == fast.total_dwell_min


def test_slower_speed_increases_exposure():
    slow = analyze_route(_plan(), speed_kmh=20)
    fast = analyze_route(_plan(), speed_kmh=80)
    assert slow.exposure_score > fast.exposure_score


# --------------------------------------------------------------------------
# Kill-zone detection
# --------------------------------------------------------------------------

def test_killzone_detected_on_threat_choke_dwell():
    rr = analyze_route(_plan())
    assert rr.choke_kill_zones, "expected at least one kill-zone"


def test_killzone_label_format():
    rr = analyze_route(_plan())
    for kz in rr.choke_kill_zones:
        assert "->" in kz


def test_no_killzone_on_low_threat_choke():
    p = ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.2),
               Stop("B", 0, 0.5, threat_score=0.3, choke_point=True, dwell_min=10),
               Stop("C", 0, 1.0, threat_score=0.2)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)],
    )
    rr = analyze_route(p)
    assert rr.choke_kill_zones == []


def test_killzone_high_threat_choke_no_dwell():
    # threat >= 0.7 choke with zero dwell still counts (forced-slow kill-zone).
    p = ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.2),
               Stop("B", 0, 0.5, threat_score=0.75, choke_point=True, dwell_min=0),
               Stop("C", 0, 1.0, threat_score=0.2)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)],
    )
    rr = analyze_route(p)
    assert any("B" in kz for kz in rr.choke_kill_zones)


def test_no_killzone_non_choke_high_threat():
    p = ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.2),
               Stop("B", 0, 0.5, threat_score=0.9, dwell_min=20),  # not a choke
               Stop("C", 0, 1.0, threat_score=0.2)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)],
    )
    rr = analyze_route(p)
    assert rr.choke_kill_zones == []


# --------------------------------------------------------------------------
# Policy / over-policy / escort
# --------------------------------------------------------------------------

def test_over_policy_counted():
    rr = analyze_route(_plan(ceiling=0.7))
    # Mid->Hot and Hot->End involve 0.8 threat > 0.7 ceiling -> 2 over-policy.
    assert rr.over_policy_legs == 2


def test_no_over_policy_when_ceiling_high():
    rr = analyze_route(_plan(ceiling=0.95))
    assert rr.over_policy_legs == 0


def test_escort_flag_respects_threshold():
    rr = analyze_route(_plan(escort=0.5))
    # leg0 threat 0.55 >= 0.5 -> escort
    assert rr.legs[0].escort_required is True


def test_escort_flag_false_below_threshold():
    rr = analyze_route(_plan(escort=0.9))
    assert all(not l.escort_required for l in rr.legs)


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------

def test_recommendations_nonempty():
    rr = analyze_route(_plan())
    assert rr.recommendations


def test_recommendations_mention_killzone():
    rr = analyze_route(_plan())
    joined = " ".join(rr.recommendations).lower()
    assert "kill-zone" in joined or "ambush" in joined


def test_recommendations_mention_over_policy():
    rr = analyze_route(_plan(ceiling=0.5))
    joined = " ".join(rr.recommendations).lower()
    assert "policy" in joined


def test_recommendations_clean_route():
    p = ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.1),
               Stop("B", 0, 0.2, threat_score=0.15)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)],
    )
    rr = analyze_route(p)
    joined = " ".join(rr.recommendations).lower()
    assert "within policy" in joined or "standard" in joined


def test_recommendations_refuel():
    p = ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.1),
               Stop("B", 0, 5.0, threat_score=0.1)],
        vehicles=[Vehicle("v", "T", 10, 0.5)],  # tiny range
    )
    rr = analyze_route(p)
    joined = " ".join(rr.recommendations).lower()
    assert "refuel" in joined or "range" in joined
    assert rr.needs_refuel is True


def test_recommendations_dwell_reduction():
    p = ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.2),
               Stop("B", 0, 0.5, threat_score=0.6, dwell_min=30),
               Stop("C", 0, 1.0, threat_score=0.2)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)],
    )
    rr = analyze_route(p)
    joined = " ".join(rr.recommendations).lower()
    assert "dwell" in joined


# --------------------------------------------------------------------------
# compare_routes
# --------------------------------------------------------------------------

def _routes():
    a = analyze_route(load_plan(str(RC / "alpha-direct")), name="alpha")
    b = analyze_route(load_plan(str(RC / "bravo-bypass")), name="bravo")
    c = analyze_route(load_plan(str(RC / "charlie-night")), name="charlie")
    return [a, b, c]


def test_compare_candidate_count():
    cmp = compare_routes(_routes())
    assert cmp["candidates"] == 3


def test_compare_ranking_length():
    cmp = compare_routes(_routes())
    assert len(cmp["ranking"]) == 3


def test_compare_recommends_lowest_exposure_within_policy():
    cmp = compare_routes(_routes())
    # bravo avoids the choke entirely -> lowest exposure -> recommended.
    assert cmp["recommended"] == "bravo"


def test_compare_charlie_beats_alpha():
    # Same geometry; charlie has less dwell in the threat band -> ranks higher.
    cmp = compare_routes(_routes())
    rank = cmp["ranking"]
    assert rank.index("charlie") < rank.index("alpha")


def test_compare_rationale_present():
    cmp = compare_routes(_routes())
    assert cmp.get("rationale")
    assert "margin" in cmp


def test_compare_single_route():
    cmp = compare_routes([analyze_route(_plan(), name="solo")])
    assert cmp["candidates"] == 1
    assert cmp["recommended"] == "solo"
    assert "only candidate" in cmp["rationale"]


def test_compare_over_policy_deprioritised():
    # A clean long route should beat a short over-policy route.
    clean = analyze_route(ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.2),
               Stop("B", 0, 2.0, threat_score=0.3),
               Stop("C", 0, 4.0, threat_score=0.25)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)], max_threat_per_leg=0.7),
        name="clean")
    dirty = analyze_route(ConvoyPlan(
        stops=[Stop("A", 0, 0, threat_score=0.2),
               Stop("B", 0, 0.3, threat_score=0.95)],
        vehicles=[Vehicle("v", "T", 1e6, 0.1)], max_threat_per_leg=0.7),
        name="dirty")
    cmp = compare_routes([dirty, clean])
    assert cmp["recommended"] == "clean"


def test_compare_routes_dict_keyed_by_name():
    cmp = compare_routes(_routes())
    assert set(cmp["routes"].keys()) == {"alpha", "bravo", "charlie"}


def test_compare_deterministic():
    assert compare_routes(_routes()) == compare_routes(_routes())


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------

def test_routerisk_to_dict_keys():
    d = analyze_route(_plan()).to_dict()
    for k in ("name", "total_km", "risk_index", "band", "exposure_score",
              "legs", "choke_kill_zones", "recommendations", "over_policy_legs"):
        assert k in d


def test_legrisk_to_dict_rounding():
    d = analyze_route(_plan()).legs[0].to_dict()
    assert isinstance(d["exposure"], float)
    assert d["threat"] == round(d["threat"], 3)


def test_comparison_json_roundtrip():
    cmp = compare_routes(_routes())
    s = json.dumps(cmp)
    assert json.loads(s) == cmp


# --------------------------------------------------------------------------
# Renderers
# --------------------------------------------------------------------------

def test_markdown_has_ranking_table():
    md = to_markdown(compare_routes(_routes()))
    assert "# Convoy route-risk brief" in md
    assert "Ranking" in md
    assert "Recommended route" in md


def test_markdown_lists_each_route():
    md = to_markdown(compare_routes(_routes()))
    for name in ("alpha", "bravo", "charlie"):
        assert f"`{name}`" in md


def test_markdown_leg_labels_present():
    md = to_markdown(compare_routes(_routes()))
    # Leg rows must show actual from->to labels, not a placeholder.
    assert "FOB GATEWAY->" in md
    assert "XXX" not in md


def test_markdown_is_utf8_encodable():
    md = to_markdown(compare_routes(_routes()))
    md.encode("utf-8")  # markdown is written as UTF-8; must round-trip


def test_console_ascii_safe():
    out = to_console(compare_routes(_routes()))
    out.encode("ascii")


def test_console_has_banner():
    out = to_console(compare_routes(_routes()))
    assert "ROUTE-RISK BRIEF" in out
    assert "not a targeting" in out.lower()


# --------------------------------------------------------------------------
# load_plan / _route_name
# --------------------------------------------------------------------------

def test_load_plan_from_dir():
    p = load_plan(str(RC / "alpha-direct"))
    assert isinstance(p, ConvoyPlan)
    assert len(p.stops) == 5


def test_load_plan_from_file():
    p = load_plan(str(RC / "alpha-direct" / "plan.json"))
    assert len(p.stops) == 5


def test_load_plan_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_plan(str(RC / "does-not-exist"))


def test_route_name_from_dir():
    assert _route_name(str(RC / "alpha-direct")) == "alpha-direct"


def test_route_name_from_file():
    name = _route_name(str(RC / "alpha-direct" / "plan.json"))
    assert "plan" in name


# --------------------------------------------------------------------------
# CLI (risk_main)
# --------------------------------------------------------------------------

def test_cli_single_console(capsys):
    rc = risk_main([str(D / "05-high-threat-corridor")])
    assert rc == 0
    assert "ROUTE-RISK BRIEF" in capsys.readouterr().out


def test_cli_compare_json(capsys):
    rc = risk_main([str(RC / "alpha-direct"), str(RC / "bravo-bypass"),
                    "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["candidates"] == 2
    assert data["recommended"] == "bravo-bypass"


def test_cli_markdown(capsys):
    rc = risk_main([str(RC / "alpha-direct"), "--format", "markdown"])
    assert rc == 0
    assert "# Convoy route-risk brief" in capsys.readouterr().out


def test_cli_out_file(tmp_path, capsys):
    out = tmp_path / "brief.json"
    rc = risk_main([str(RC / "bravo-bypass"), "--format", "json", "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["recommended"] == "bravo-bypass"


def test_cli_missing_target(tmp_path):
    rc = risk_main([str(tmp_path / "nope")])
    assert rc == 1


def test_cli_invalid_plan(tmp_path):
    bad = tmp_path / "plan.json"
    bad.write_text("{ not json", encoding="utf-8")
    rc = risk_main([str(tmp_path)])
    assert rc == 1


def test_cli_plan_missing_stops(tmp_path):
    bad = tmp_path / "plan.json"
    bad.write_text(json.dumps({"vehicles": []}), encoding="utf-8")
    rc = risk_main([str(tmp_path)])
    assert rc == 1


def test_cli_speed_flag(capsys):
    rc = risk_main([str(RC / "alpha-direct"), "--speed", "60", "--format", "json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["candidates"] == 1


def test_cli_default_target(monkeypatch, tmp_path, capsys):
    # Default target "." — write a plan in cwd.
    (tmp_path / "plan.json").write_text(
        json.dumps({"stops": [{"name": "A", "lat": 0, "lon": 0},
                              {"name": "B", "lat": 0, "lon": 1}],
                    "vehicles": []}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = risk_main([])
    assert rc == 0
    assert "ROUTE-RISK BRIEF" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Demo integration — every compare demo loads & analyses cleanly
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["alpha-direct", "bravo-bypass", "charlie-night"])
def test_compare_demo_loads(name):
    rr = analyze_route(load_plan(str(RC / name)), name=name)
    assert rr.total_km > 0
    assert rr.legs


def test_compare_demo_scenario_exists():
    assert (RC / "SCENARIO.md").exists()


@pytest.mark.parametrize("demo", [
    "01-mixed", "02-fuel-shortfall", "03-djibouti-port-run",
    "04-mountain-chokepoint", "05-high-threat-corridor", "06-multimodal-refuel",
    "07-hadr-flood-relief", "09-max-risk-corridor",
])
def test_existing_demos_analyse(demo):
    rr = analyze_route(load_plan(str(D / demo)), name=demo)
    assert isinstance(rr, RouteRisk)
    assert 0 <= rr.risk_index <= 100
