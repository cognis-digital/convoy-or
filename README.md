# convoy-or — Military convoy / logistics OR

[![CI](https://github.com/cognis-digital/convoy-or/workflows/CI/badge.svg)](https://github.com/cognis-digital/convoy-or/actions)
[![Classification](https://img.shields.io/badge/classification-UNCLASSIFIED-green.svg)](./UPSTREAM.md)

> Plan and audit convoys: route distance, fuel, threat exposure, escort requirements, choke points. OR-Tools compatible.

## Usage — step by step

`convoy-or` evaluates a convoy/logistics plan against policy bounds (fuel, threat exposure, escort, chokepoints) and emits findings in your choice of format.

1. **Install** (from PyPI or a local checkout):

   ```bash
   pip install cognis-convoy-or      # or: pip install -e .
   convoy-or --version
   ```

2. **Run a scan** — point it at a directory containing a `plan.json` (or at the file's parent). The positional `target` defaults to `.`:

   ```bash
   convoy-or ./mission --format console
   ```

3. **Get machine-readable output** — switch the format and write to a file. Supported: `console`, `json`, `markdown`, `sarif`, `oscal`:

   ```bash
   convoy-or ./mission --format json --out convoy-findings.json
   ```

4. **Read the result** — each finding has an id (e.g. `CV-FUEL`, `CV-THREAT`, `CV-ESCORT`, `CV-CHOKE`), a NIST-800-30 severity, and a location. Inspect the JSON:

   ```bash
   jq '.findings[] | {id, severity, message}' convoy-findings.json
   ```

5. **Gate it in CI** — make the process exit non-zero when anything at/above a severity is found via `--fail-on` (`very_high`|`high`|`moderate`|`low`|`none`):

   ```bash
   convoy-or ./mission --format sarif --out convoy.sarif --fail-on high \
     --classification "UNCLASSIFIED//FOR PUBLIC RELEASE"
   ```

## Upstream

Forks / wraps **https://github.com/google/or-tools**. See [`UPSTREAM.md`](./UPSTREAM.md) for the
licensing posture, supported commits, and how to upgrade.

## What this adds for military / IC use

- Convoy plan evaluator (distance / fuel / threat)
- Escort-required check above configurable threat threshold
- Choke-point dwell minimization
- OR-Tools VRP integration (when installed)

## Install

```bash
# Shared library (only once for the whole ecosystem):
pip install -e ../../shared

# This tool:
pip install -e .
```

## Demo

```bash
convoy-or demos/01-mixed/
```

Outputs are available in five formats — all respect an operator-supplied
classification banner (passed via `--classification`):

```bash
convoy-or <target> --format=console     # default
convoy-or <target> --format=json
convoy-or <target> --format=sarif       # for code-scanning pipelines
convoy-or <target> --format=markdown    # for PRs / briefings
convoy-or <target> --format=oscal       # OSCAL Assessment Results skeleton
```

## Classification banner

All output is wrapped with an operator-supplied classification banner.
**Default**: `UNCLASSIFIED//FOR PUBLIC RELEASE`.

> ⚠️ This tool **does not** generate or validate the *content* of higher
> classifications. Operators on cleared systems supply real markings at runtime.
> See [`../shared/cognis_mil/classmark.py`](../../shared/cognis_mil/classmark.py).

## Compliance crosswalks (built in)

Every finding can carry references to:
- **NIST 800-53 Rev 5** controls (e.g. `AC-2(1)`)
- **DISA STIG** rule IDs (e.g. `V-242414`)
- **MITRE ATT&CK** technique IDs (e.g. `T1078`)
- **CCI** (Control Correlation Identifier)

These are emitted in JSON, SARIF, and the OSCAL skeleton.

## CI / RMF integration

```yaml
- name: convoy-or scan
  run: |
    pip install cognis-convoy-or
    convoy-or . --format=oscal --out=assessment-results.json --fail-on=high
- name: Upload to eMASS/Xacta
  run: cognis-rmf-package import assessment-results.json
```

## Part of the Cognis Digital military / IC ecosystem

12 repos. All MIT/Apache-2.0/GPL-3 (per upstream). Cognis additions are
Apache-2.0 unless stated otherwise.

See [the master index](../../MASTER-INDEX.md).

## Interoperability

`convoy-or` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `convoy-or`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.
