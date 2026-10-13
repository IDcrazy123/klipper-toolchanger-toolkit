# Quick start

Python 3.10+ and a reviewed Klipper printer profile. Generates test patches, an SVG preview and a Z report; no printed labels or ticks.

## 1. Install

Extract the latest ZIP from **Other files**. Upload `oxplow_runtime.cfg` beside `printer.cfg` and add:

```ini
[include oxplow_runtime.cfg]
```

Save & Restart while idle, then verify in Console:

```gcode
_OXPLOW_CHECK VERSION=2.3.2 STAGE=install
```

Continue after `runtime installed`. Use Python and cfg from the same ZIP.

## 2. Generate

Open a terminal in the extracted folder; replace YOUR_PRINTER with your Moonraker address:

```text
python generate_oxplow_gcode.py discover --url http://YOUR_PRINTER:7125 -o profiles/my-printer.local.json
```

Edit JSON for your actual macros, safe area, temperatures and retract/lift state. Set `reviewed=true` after reviewing your own profile.

```text
python generate_oxplow_gcode.py validate --profile profiles/my-printer.local.json --url http://YOUR_PRINTER:7125
python generate_oxplow_gcode.py generate --profile profiles/my-printer.local.json -o output/test.gcode
```

Resolve errors and inspect the SVG before printing.

## 3. Print and read

Clear the bed, check filament and start with one tool. Upload `test.gcode` via G-code Files. Your start macro handles its own prime.

**Left → right (+X): increasing tool ID**, T0 → T1 → T2…; skipped IDs stay skipped. Use the SVG/report to identify patches.

Within each patch, row 0 is at lowest Y (usually front). Default Z decreases toward higher Y (rear); `low-to-high` reverses it. Choose smooth joined rows without gaps or ridges:

```text
python generate_oxplow_gcode.py calculate --report output/test.report.json --tool 0 --row 35
```

If hard to count, use `--distance 12.0` instead: mm from the center of the lowest-Y row to your chosen area. Positive correction raises the nozzle; negative lowers it. Save through your printer's offset procedure and confirm with `ramp_range=0`; the toolkit does not save offsets automatically.

Full setup, troubleshooting and Vietnamese instructions are in README.md and docs inside the ZIP. Experimental: verify your physical patch before applying a result.

Oxplow method by Maxim7745; remix by Công Dương.
