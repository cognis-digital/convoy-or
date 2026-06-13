# convoy-or — Military convoy / logistics OR

[![CI](https://github.com/cognis-digital/convoy-or/workflows/CI/badge.svg)](https://github.com/cognis-digital/convoy-or/actions)
[![Classification](https://img.shields.io/badge/classification-UNCLASSIFIED-green.svg)](./UPSTREAM.md)

> Plan and audit convoys: route distance, fuel, threat exposure, escort requirements, choke points. OR-Tools compatible.

<!-- cognis:layman:start -->
## What is this?

convoy-or is a command-line tool that helps military planners review and audit convoy routes before a mission. You give it a route plan — a list of stops with coordinates and threat ratings — and it tells you if the convoy has enough fuel, where the dangerous chokepoints are, and whether you need additional escort vehicles. It is aimed at military logisticians, defense analysts, and operations staff who need a quick, automated sanity-check on ground movement plans.
<!-- cognis:layman:end -->

## Upstream

Forks / wraps **https://github.com/google/or-tools**. See [`UPSTREAM.md`](./UPSTREAM.md) for the
licensing posture, supported commits, and how to upgrade.

## What this adds for military / IC use

- Convoy plan evaluator (distance / fuel / threat)
- Escort-required check above configurable threat threshold
- Choke-point dwell minimization
- OR-Tools VRP integration (when installed)

<!-- cognis:domains:start -->
## Domains

**Primary domain:** Defense & Aerospace  ·  **JTF MERIDIAN division:** IRONCLAD · INDIA

**Topics:** `cognis` `defense` `aerospace` `defense-tech` `threat-intel` `compliance`

Part of the **Cognis Neural Suite** — 300+ source-available tools organized across 12 domains under the JTF MERIDIAN command structure. See the [suite on GitHub](https://github.com/cognis-digital) and [jtf-meridian](https://github.com/cognis-digital/jtf-meridian) for how the pieces fit together.
<!-- cognis:domains:end -->

<!-- cognis:install:start -->
## Install

`convoy-or` is source-available (not published to PyPI) — every method below installs
straight from GitHub. Pick whichever you prefer; the one-line scripts auto-detect
the best tool available on your machine.

**One-liner (Linux / macOS):**
```sh
curl -fsSL https://raw.githubusercontent.com/cognis-digital/convoy-or/HEAD/install.sh | sh
```

**One-liner (Windows PowerShell):**
```powershell
irm https://raw.githubusercontent.com/cognis-digital/convoy-or/HEAD/install.ps1 | iex
```

**Or install manually — any one of:**
```sh
pipx install "git+https://github.com/cognis-digital/convoy-or.git"     # isolated (recommended)
uv tool install "git+https://github.com/cognis-digital/convoy-or.git"  # uv
pip install "git+https://github.com/cognis-digital/convoy-or.git"      # pip
```

**From source:**
```sh
git clone https://github.com/cognis-digital/convoy-or.git
cd convoy-or && pip install .
```

Then run:
```sh
convoy-or --help
```
<!-- cognis:install:end -->

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
    pip install "git+https://github.com/cognis-digital/convoy-or.git"
    convoy-or . --format=oscal --out=assessment-results.json --fail-on=high
- name: Upload to eMASS/Xacta
  run: cognis-rmf-package import assessment-results.json
```

## Part of the Cognis Digital military / IC ecosystem

12 repos. All MIT/Apache-2.0/GPL-3 (per upstream). Cognis additions are
Apache-2.0 unless stated otherwise.

See [the master index](../../MASTER-INDEX.md).

<a name="verification"></a>
## Verification

[![tests](https://img.shields.io/badge/tests-3%20passing-2ea44f.svg)](AUDIT.md)

Every push is verified end-to-end. Latest audit (2026-06-13):

```text
tests        : 3 passed, 0 failed, 0 errored
compile      : all modules parse
cli          : convoy-or 0.1.0
package      : convoy_or
```

<details><summary>CLI surface (<code>--help</code>)</summary>

```text
usage: convoy-or [-h] [--format {console,json,markdown,sarif,oscal}]
                 [--out OUT] [--fail-on {very_high,high,moderate,low,none}]
                 [--classification CLASSIFICATION] [-v]
                 [target]

convoy-or — Cognis Digital · Military/IC ecosystem

positional arguments:
  target                Path/target

options:
  -h, --help            show this help message and exit
  --format {console,json,markdown,sarif,oscal}
  --out OUT             Write output to file
```
</details>

Full machine-readable results: [`AUDIT.md`](AUDIT.md) · regenerate with `python -m convoy_or --help` + `pytest -q`.

<div align="right"><a href="#top">↑ back to top</a></div>

