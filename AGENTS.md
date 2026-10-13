# Repository development rules

Read README.md, WORKFLOW.md and the target project's README/AGENTS.md before editing. Inspect Git status; preserve unrelated changes. Work only in the requested project unless shared infrastructure needs a stated change.

Python 3.10+, standard library for runtime builders. Add dependencies only for a clear need; Jinja2 here is a pinned test dependency. Research the actual firmware/plugin revision using primary sources. Start/end/select macros and extrusion recovery are machine contracts, not global defaults.

For Z, extrusion, heating, tool selection or bounds changes: preserve previous source locally, record trigger/cause/fix/risks, add scenario regression tests, inspect output/preview and run appropriate checks. No physical-stability claim from software tests. Keep example profiles reviewed=false; synthetic test profiles are never released as real-machine output.

Never publish private machine profiles, network addresses, API keys, raw macro evidence or generated printer output. Release ZIPs use allowlists and manifests. Only the authorized purge photographs in projects/purge-lines/photos are deliberately public; other hardware evidence remains local.

Do not send G-code, install/restart firmware, save offsets, print, commit/push/publish or change repository access unless the user authorizes the action in the session. Carry specifically authorized work to completion without asking the same permission again.

Oxplow 2.3.2 is preserved and paused. Do not silently change its source/version or manifest. Reactivate it only for a concrete request, with versioned release changes. Keep shared WORKFLOW copies consistent when they are intentionally updated; frozen release docs require a new release rather than unnoticed edits.

No subagents unless the user or a task-specific instruction requests them. Report software checks separately from actual machine runs and state remaining limitations. Use project release records and component licensing; never apply one license indiscriminately to all imported work.
