# Release procedure

1. Identify target project and exact revision. Read Git status; do not include unrelated edits. Confirm publication is authorized.
2. Run relevant tests, required upstream integrations and preview/report checks. Record Python/firmware revisions and skip counts. Hardware results are separate.
3. Update version, CHANGELOG, affected instructions, provenance and license mapping. Keep preserved releases immutable unless a new version is explicitly prepared.
4. Build with the project allowlist, never zip the entire workspace. Verify MANIFEST.sha256.json after extracting into a fresh directory, check included filenames and run extracted tests.
5. Run scripts/check_public.py against the intended tracked file list. Inspect staged Git diff and any binary/photo additions. Profiles, generated machine output, addresses, credentials and logs must be absent.
6. Commit only the reviewed public tree. Publish repository or Printables artifacts within the user's authorized scope. Preserve versions the owner asked to retain.
7. Verify the public project name/version, files, instructions and photos. Keep local hashes and publication evidence. If download verification is blocked, state that limit rather than claiming a round-trip hash match.

Purge 1.0.0 remains experimental until its community macro has a separately authorized physical trial. Original photographs are not a substitute. Oxplow 2.3.2 is a preserved release with its recorded component provenance.
