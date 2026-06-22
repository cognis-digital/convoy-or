"""GeoJSON (RFC 7946) export tests."""
from pathlib import Path

from convoy_or.core import ConvoyPlan, Stop, Vehicle
from convoy_or.geojson import _load_plan, map_main, plan_to_geojson

D = Path(__file__).parent.parent / "demos"


def _plan():
    return ConvoyPlan(
        stops=[
            Stop("A", 34.0, -117.0, threat_score=0.1),
            Stop("B", 34.5, -117.5, threat_score=0.45, choke_point=True),
            Stop("C", 35.0, -118.0, threat_score=0.8),
        ],
        vehicles=[Vehicle("v", "MRAP", 500, 0.5)],
        max_threat_per_leg=0.7,
        escort_required_above_threat=0.4,
    )


def test_feature_collection_shape():
    gj = plan_to_geojson(_plan())
    assert gj["type"] == "FeatureCollection"
    kinds = [f["properties"]["kind"] for f in gj["features"]]
    assert kinds.count("stop") == 3
    assert kinds.count("leg") == 2
    assert kinds.count("route") == 1


def test_coordinate_order_is_lon_lat():
    gj = plan_to_geojson(_plan())
    stop = next(f for f in gj["features"] if f["properties"]["name"] == "A")
    # RFC 7946 §3.1.1: [longitude, latitude]
    assert stop["geometry"]["coordinates"] == [-117.0, 34.0]


def test_geometry_types_valid():
    gj = plan_to_geojson(_plan())
    for f in gj["features"]:
        assert f["type"] == "Feature"
        assert f["geometry"]["type"] in {"Point", "LineString"}


def test_leg_policy_flags():
    gj = plan_to_geojson(_plan())
    legs = [f for f in gj["features"] if f["properties"]["kind"] == "leg"]
    # Leg B->C has threat 0.8 > 0.7 ceiling and >= 0.4 escort threshold.
    bc = next(l for l in legs if l["properties"]["to"] == "C")
    assert bc["properties"]["over_policy"] is True
    assert bc["properties"]["escort_required"] is True
    assert bc["properties"]["threat_band"] == "high"


def test_threat_band_thresholds():
    gj = plan_to_geojson(_plan())
    stops = {f["properties"]["name"]: f["properties"]["threat_band"]
             for f in gj["features"] if f["properties"]["kind"] == "stop"}
    assert stops["A"] == "low"      # 0.1
    assert stops["B"] == "medium"   # 0.45
    assert stops["C"] == "high"     # 0.8


def test_loads_real_demo():
    plan = _load_plan(str(D / "01-mixed"))
    gj = plan_to_geojson(plan)
    assert len(gj["features"]) >= 4


def test_map_main_to_file(tmp_path, capsys):
    out = tmp_path / "route.geojson"
    rc = map_main([str(D / "01-mixed"), "--out", str(out)])
    assert rc == 0
    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"


def test_map_main_missing_plan(tmp_path):
    rc = map_main([str(tmp_path)])
    assert rc == 1
