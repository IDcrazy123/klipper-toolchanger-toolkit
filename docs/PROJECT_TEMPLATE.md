# New project template

Create projects/<slug>/ with README.md, AGENTS.md, CHANGELOG.md, component LICENSE/provenance, source entry point, profiles/*.example.json, tests/test_*.py and docs/CONFIGURATION.md, VALIDATION.md, SOURCES.md, WORKFLOW.md. Add templates only when useful; photos require explicit publication authorization.

Define:

- Objective, firmware/plugin compatibility and unsupported cases.
- Inputs/outputs, units and schema; reject unknown/nonfinite/ambiguous data.
- Reviewed-profile gate; synthetic tests are labeled and never installed on real machines.
- Machine contracts for start/end/tool selection, offsets, heaters and E/retract recovery.
- Bounds/flow/temperature checks and what they cannot detect.
- Regression cases, preview/report review and software/hardware evidence distinction.
- Source revision, attribution, component license and publication allowlist.
- CLI errors, no-overwrite behavior and package manifest/extraction checks.
- Versioning, migration, support/bug-report path and release status.

Register the project/version/status in projects.json and README. Add a focused CI job, then package and test the extracted result before publishing. Keep credentials and machine records local.
