"""Every shipped demo must produce its documented finding set."""
from pathlib import Path

import pytest

from convoy_or.core import scan

D = Path(__file__).parent.parent / "demos"

# demo dir -> set of finding ids that MUST be present
EXPECTED = {
    "01-mixed": {"CV-THREAT", "CV-CHOKE", "CV-ESCORT"},
    "02-fuel-shortfall": {"CV-FUEL"},
    "03-djibouti-port-run": {"CV-OK"},
    "04-mountain-chokepoint": {"CV-CHOKE", "CV-ESCORT"},
    "05-high-threat-corridor": {"CV-THREAT", "CV-ESCORT"},
    "06-multimodal-refuel": {"CV-OK"},
    "07-hadr-flood-relief": {"CV-CHOKE", "CV-ESCORT"},
    "08-noplan-template": {"CV-NOPLAN"},
    "09-max-risk-corridor": {"CV-FUEL", "CV-THREAT", "CV-ESCORT", "CV-CHOKE"},
}


@pytest.mark.parametrize("demo,expected", EXPECTED.items())
def test_demo_findings(demo, expected):
    r = scan(str(D / demo))
    ids = {f.id for f in r.findings}
    assert expected.issubset(ids), f"{demo}: got {ids}, expected superset of {expected}"


def test_all_demos_have_scenario():
    for demo in EXPECTED:
        assert (D / demo / "SCENARIO.md").exists(), f"{demo} missing SCENARIO.md"
