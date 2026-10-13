# Klipper Toolchanger Toolkit

Reusable Klipper tools developed from reviewed personal configurations. Each project has its own version, profile contract, tests, documentation and release ZIP. Receiving machines require their own reviewed configuration; the repository name is not a compatibility promise for every firmware or toolchanger.

| Project | Version | Status | Entry |
|---|---|---|---|
| [Oxplow first-layer Z calibration](projects/oxplow/README.md) | 2.3.2 | Development paused; preserved release | `generate_oxplow_gcode.py` |
| [Toolchanger purge lines](projects/purge-lines/README.md) | 1.0.0 | Experimental community builder | `build_purge.py` |

Oxplow makes patch-only ramps, an SVG and a row-to-Z report. Purge Lines makes a reviewed cfg, fixed numeric tool slots, SVG/report and an explicit retract/recovery contract. Neither builder installs files or starts a printer.

## Start here

Read the chosen project's README. Copy an unreviewed example to a **local** profile, review your actual machine, then generate and inspect output. Start with one tool after clearing the intended area. Physical printing needs separate operator authorization and validation.

Python 3.10+; builders use the standard library. Development tests additionally use the pinned Jinja2 dependency:

```text
python -m pip install -r requirements-dev.txt
python scripts/run_tests.py
```

For four optional upstream Klipper dispatcher tests, set `OXPLOW_KLIPPER_SOURCE` to a checkout containing `gcode.py` and `extras/gcode_macro.py` from the pinned revision in CI. A skipped integration test is not a pass claim.

## Repository structure

```text
projects/<project>/   source, README, docs, tests, profiles, templates
docs/                shared architecture, release policy and project template
scripts/             test runner and publication checks
.github/             CI, issue and pull-request templates
```

Private profiles, printer addresses, credentials, raw evidence and generated machine output stay outside commits. Release packages use project allowlists and SHA256 manifests. Purge photographs were explicitly supplied by their owner for publication; they show the original macro, not hardware validation of the community revision.

Development: [WORKFLOW](WORKFLOW.md), [CONTRIBUTING](CONTRIBUTING.md), [ARCHITECTURE](docs/ARCHITECTURE.md), [RELEASING](docs/RELEASING.md), [AGENTS](AGENTS.md). Licensing is per component: [LICENSES](LICENSES.md). [Vietnamese overview](README.vi.md).
