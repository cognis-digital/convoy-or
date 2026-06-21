"""OSCAL 1.1.2 Assessment Results export (cognis_mil) — real, validatable."""
import json
from cognis_mil.models import ScanResult, Finding, Severity
from cognis_mil.exporters import to_oscal, to_oscal_skeleton


def _result():
    r = ScanResult(tool_name="tool", tool_version="0.1.0")
    r.started_at = 1750000000
    r.add(Finding("F-1", Severity.HIGH, "Example weakness", nist_800_53="AC-6",
                  disa_stig="V-1", cci="CCI-1"))
    r.finalize()
    return r


def test_oscal_real_shape():
    ar = json.loads(to_oscal(_result()))["assessment-results"]
    assert ar["metadata"]["oscal-version"] == "1.1.2"
    assert len(ar["uuid"]) == 36
    res = ar["results"][0]
    assert res["findings"][0]["target"]["status"]["state"] == "not-satisfied"


def test_no_zero_uuid_placeholder():
    assert "00000000-0000-0000-0000-000000000000" not in to_oscal(_result())


def test_deterministic():
    assert to_oscal(_result()) == to_oscal(_result())


def test_alias():
    assert to_oscal_skeleton is to_oscal
