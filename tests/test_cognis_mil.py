"""Coverage for the shared cognis_mil library: models, audit, classmark, exporters."""
import json

import pytest

from cognis_mil import (
    AuditLog, ClassificationBanner, Finding, ScanResult, Severity,
    to_console, to_json, to_markdown, to_sarif, to_oscal_skeleton,
)
from cognis_mil.models import WEIGHTS


# --------------------------------------------------------------------------
# Severity / Finding / ScanResult
# --------------------------------------------------------------------------

def test_severity_critical_alias():
    assert Severity.CRITICAL == Severity.VERY_HIGH


def test_finding_weight_autofilled():
    f = Finding("X", Severity.HIGH, "t")
    assert f.weight == WEIGHTS[Severity.HIGH]


def test_finding_accepts_string_severity():
    f = Finding("X", "moderate", "t")
    assert f.severity == Severity.MODERATE


def test_finding_to_dict_severity_is_string():
    d = Finding("X", Severity.LOW, "t").to_dict()
    assert d["severity"] == "low"


def test_scanresult_empty_finalize():
    r = ScanResult(tool_name="t").finalize()
    assert r.composite_score == 0.0
    assert r.risk_level == "Very Low"


def test_scanresult_score_increases_with_findings():
    r = ScanResult(tool_name="t")
    r.add(Finding("A", Severity.VERY_HIGH, "a"))
    r.add(Finding("B", Severity.VERY_HIGH, "b"))
    r.finalize()
    assert r.composite_score > 0


def test_scanresult_score_capped_at_100():
    r = ScanResult(tool_name="t")
    for i in range(50):
        r.add(Finding(f"F{i}", Severity.VERY_HIGH, "x"))
    r.finalize()
    assert r.composite_score == 100.0


def test_scanresult_risk_level_bands():
    r = ScanResult(tool_name="t")
    r.add(Finding("A", Severity.VERY_HIGH, "a"))
    r.finalize()
    assert r.risk_level in {"Low", "Moderate", "High", "Very High", "Very Low"}


def test_scanresult_total_findings():
    r = ScanResult(tool_name="t")
    r.add(Finding("A", Severity.LOW, "a"))
    assert r.total_findings() == 1


def test_scanresult_to_dict_classification():
    r = ScanResult(tool_name="t")
    d = r.to_dict()
    assert "classification" in d
    assert d["tool_name"] == "t"


# --------------------------------------------------------------------------
# Exporters
# --------------------------------------------------------------------------

def _res():
    r = ScanResult(tool_name="conv", tool_version="0.1.0")
    r.add(Finding("F-1", Severity.HIGH, "weak", nist_800_53="AC-6",
                  disa_stig="V-1", mitre_attack="T1078", cci="CCI-1",
                  location="x", remediation="fix it"))
    r.finalize()
    return r


def test_to_json_valid():
    d = json.loads(to_json(_res()))
    assert d["findings"][0]["id"] == "F-1"


def test_to_console_contains_id():
    out = to_console(_res())
    assert "F-1" in out


def test_to_markdown_table():
    out = to_markdown(_res())
    assert "| Sev | ID |" in out
    assert "F-1" in out


def test_to_sarif_valid():
    d = json.loads(to_sarif(_res()))
    assert d["version"] == "2.1.0"
    assert d["runs"][0]["results"][0]["ruleId"] == "F-1"


def test_to_sarif_severity_mapping():
    d = json.loads(to_sarif(_res()))
    assert d["runs"][0]["results"][0]["level"] == "error"  # HIGH -> error


def test_to_oscal_skeleton_alias_runs():
    d = json.loads(to_oscal_skeleton(_res()))
    assert "assessment-results" in d


# --------------------------------------------------------------------------
# AuditLog — hash-chain
# --------------------------------------------------------------------------

def test_audit_append_returns_hash(tmp_path):
    log = AuditLog(tmp_path / "a.log")
    e = log.append({"event": "scan", "n": 1})
    assert "hash" in e and len(e["hash"]) == 64


def test_audit_genesis_prev(tmp_path):
    log = AuditLog(tmp_path / "a.log")
    e = log.append({"x": 1})
    assert e["prev"] == "GENESIS"


def test_audit_chain_links(tmp_path):
    log = AuditLog(tmp_path / "a.log")
    e1 = log.append({"x": 1})
    e2 = log.append({"x": 2})
    assert e2["prev"] == e1["hash"]


def test_audit_verify_ok(tmp_path):
    log = AuditLog(tmp_path / "a.log")
    log.append({"x": 1})
    log.append({"x": 2})
    log.append({"x": 3})
    ok, msg = log.verify()
    assert ok is True
    assert "3" in msg


def test_audit_verify_empty(tmp_path):
    ok, msg = AuditLog(tmp_path / "none.log").verify()
    assert ok is True


def test_audit_detects_tamper(tmp_path):
    path = tmp_path / "a.log"
    log = AuditLog(path)
    log.append({"x": 1})
    log.append({"x": 2})
    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["event"] = {"x": 999}  # tamper without recomputing hash
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    ok, msg = AuditLog(path).verify()
    assert ok is False


def test_audit_detects_corrupt_json(tmp_path):
    path = tmp_path / "a.log"
    log = AuditLog(path)
    log.append({"x": 1})
    path.write_text("{ not json\n")
    ok, msg = AuditLog(path).verify()
    assert ok is False


# --------------------------------------------------------------------------
# ClassificationBanner — shape only, no real markings
# --------------------------------------------------------------------------

def test_banner_placeholder_is_unclassified():
    b = ClassificationBanner.placeholder()
    assert b.level == "UNCLASSIFIED"
    assert "FOR PUBLIC RELEASE" in b.render()


def test_banner_validate_ok():
    ok, errs = ClassificationBanner(level="SECRET").validate()
    assert ok is True and errs == []


def test_banner_validate_bad_level():
    ok, errs = ClassificationBanner(level="ULTRA").validate()
    assert ok is False and errs


def test_banner_unclassified_with_sci_invalid():
    ok, errs = ClassificationBanner(level="UNCLASSIFIED", sci=["X"]).validate()
    assert ok is False


def test_banner_render_dissem():
    b = ClassificationBanner(level="SECRET", dissem=["NOFORN"])
    assert b.render().startswith("SECRET")
    assert "NOFORN" in b.render()


def test_banner_render_simple():
    assert ClassificationBanner(level="CONFIDENTIAL").render() == "CONFIDENTIAL"
