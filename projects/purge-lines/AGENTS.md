# Purge development rules

Read README.md, docs/CONFIGURATION.md and docs/SHARING_REVIEW.md before changes. Follow the parent repository AGENTS.md and docs/WORKFLOW.md in standalone packages.

Builder runtime stays standard library / Python 3.10+. Jinja2 is only a development test dependency. Test malformed profiles, sparse tool IDs, small rectangles, both axes, wipe parity, extrusion/flow, runtime heater limits, tool selection and current offset bounds before sharing movement changes.

Keep profiles unreviewed until their owner reviews the actual machine. Never ship synthetic test G-code/config as a real printer preset. Private machine profiles and raw logs remain outside the public tree. Photos here are explicitly authorized original-macro evidence; do not present them as hardware verification of the community revision.

Do not install/restart/print/save offsets on a user's machine without authorization for that action. A reviewed tool-selector command is a machine-specific contract, not verified mechanical motion.
