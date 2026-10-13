# Validation

27 tests passed on Windows / Python 3.14.7 / Jinja2 3.1.6, including two synthetic execution tests through upstream Klipper dispatcher revision 7bc4d09465d31cd30fc0822e8d0abe02cc8c547f. The extracted allowlist ZIP passes the same suite and SHA256 manifest checks. CI is configured for Python 3.10 and 3.14; its configured matrix is not a local claim that both versions have run.

Run from the project folder:

```text
python -m unittest discover -s tests -v
python build_purge.py validate --profile profiles/printer.example.json
```

Tests use synthetic profiles and Klipper's Jinja delimiters. They cover sparse ordering, area fit, alternating passes/wipes, nominal extrusion, unknown/nonfinite inputs, review gate, heater limits, selection availability, runtime tool/offset checks, retract sequencing and explicit exit state. The builder and generated cfg are compared through the package manifest; the unreviewed cfg template refuses the public purge entry.

Set OXPLOW_KLIPPER_SOURCE to a reviewed checkout containing gcode.py for the two dispatcher tests. Without it they are skipped; do not count those as confirmed passes. Jinja2 is a test dependency only. Synthetic temperature-wait and motion callbacks do not drive hardware or validate physical timing.

No commands from these tests reach a printer. A successful template test does not validate mechanical tool selection or transformed motion. Photos document the original owner's macro; community 1.0.0 needs one-tool, used-subset and initial-tool-last trials on the receiving machine before a hardware-verified claim.
