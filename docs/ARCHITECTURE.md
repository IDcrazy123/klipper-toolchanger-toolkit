# Architecture

Each independently versioned project owns its source, CLI, profile schema, runtime macros, preview/report mapping, tests, docs, provenance, license and release allowlist. Shared scripts coordinate checks; they do not impose one printer-start protocol on different toolchangers.

Data flow: unreviewed example → actual local profile → validation/review → local output + preview/report → operator installation/print → local feedback. Development, publication and hardware execution are separate actions.

Dependencies flow from project code to standard library and explicit test dependencies. Firmware/plugin integration is through reviewed adapters and primary-source contracts. Network discovery, when present, is read-only and endpoint-limited. No automatic scans or device writes.

Public tree contains only shareable source/examples/docs/tests and expressly authorized photos. Original machine snapshots, archives, profiles, credentials, raw logs and generated output remain outside it or under ignored paths. The monorepo can grow with another projects/<slug> directory without changing unrelated releases.
