# Contributing

1. Select one project and read its README, AGENTS and shared WORKFLOW. State the observed issue, inputs, expected/actual behavior, firmware/plugin revision and scope.
2. Preserve upstream/source attribution and previous local source. Research primary documentation or code at a recorded revision. Identify machine-specific assumptions before changing behavior.
3. Implement a small change. Separate geometry and validation from network access, printer execution and machine profiles. Do not raise limits or use FORCE_MOVE to mask errors.
4. For motion/extrusion/temperature/offset changes, add meaningful regressions for the triggering failure. Test success and rejection paths, sparse IDs, bounds, flow, modes and preview/report mapping as applicable.
5. Run project tests and publication checks. Record the environment, passed/skipped tests and hardware validation separately. Test-only dependencies do not belong in runtime installation instructions.
6. Update the project CHANGELOG, affected docs, source references and version. Build via the project allowlist, verify hashes after extraction and rerun packaged tests.
7. Open a focused PR using the template. Include sanitized evidence; keep IPs, keys, complete printer configs, local profiles and raw logs out of commits/issues. Publication requires maintainer authorization.

For a new project, start from docs/PROJECT_TEMPLATE.md and register it in projects.json. Builders must refuse unreviewed machine-ready output. Example values and synthetic fixtures must be clearly labeled. Firmware support is an explicit compatibility matrix, not the word "universal".

Oxplow is paused. Avoid unrelated cleanup inside its preserved 2.3.2 release. Purge is experimental; software results and original-macro photos do not upgrade its hardware status.
