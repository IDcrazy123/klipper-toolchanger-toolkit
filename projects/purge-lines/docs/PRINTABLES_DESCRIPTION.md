# Toolchanger Purge Lines for Klipper

Build purge macros for a reviewed toolchanger profile. Python 3.10+, no pip needed for the builder. **Experimental community version 1.0.0; photos show the original machine macro.**

1. Extract the ZIP. Copy `profiles/printer.example.json` to your local profile. Set the clear purge area, stroke axis, tool selectors/extruders, nozzle, Z, speeds and retract/recovery ownership for your actual machine. Set reviewed=true only after review.

```text
python build_purge.py validate --profile profiles/my-printer.local.json
python build_purge.py build --profile profiles/my-printer.local.json -o output/prime-lines.cfg
```

2. Inspect the SVG/report. Back up the old macro, upload the generated cfg, and include it once in printer.cfg: `[include prime-lines.cfg]`. Replace duplicate PRIME_LINES definitions. Restart while idle.

3. Your existing start macro must home/level/mesh first. Clear the purge area and test one tool before multiple tools. Example call after setup:

```gcode
M220 S100
M221 S100
PRIME_LINES INITIAL_TOOL=2 T0_TEMP=230 T2_TEMP=230
```

Only positive-temperature tools purge; the initial tool purges last and remains selected. Exit is G90/M83/E0 at travel Z, with the configured initial retract still applied. The caller/slicer must recover it once before printing; other tools also need their matching parked-retract recovery.

Tool slots increase by numeric ID along the selected axis. Solid SVG strokes extrude, dashed strokes wipe. Firmware checks cannot detect clips, objects or unsafe external toolchange macros. Full setup and Vietnamese guidance are in the ZIP. Derivative by Công Dương / IDcrazy123, based on the original prime-lines macro; code MIT, documentation/photos CC BY 4.0.
