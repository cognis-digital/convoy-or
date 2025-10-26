from pathlib import Path
from convoy_or.core import Stop, Vehicle, ConvoyPlan, evaluate_plan, haversine_km, scan
D = Path(__file__).parent.parent / "demos"
def test_haversine():
    a = Stop("a",34.0,-117.0); b = Stop("b",35.0,-118.0)
    d = haversine_km(a,b)
    assert 100 < d < 200
def test_evaluate():
    stops = [Stop("a",34.0,-117.0,threat_score=0.1),
             Stop("b",34.5,-117.5,threat_score=0.8)]
    plan = ConvoyPlan(stops=stops, vehicles=[Vehicle("v","T",500,0.3)])
    ev = evaluate_plan(plan)
    assert ev["max_threat_per_leg"] == 0.8
def test_scan_mixed():
    r = scan(str(D / "01-mixed"))
    ids = {f.id for f in r.findings}
    assert "CV-THREAT" in ids
    assert "CV-CHOKE" in ids
