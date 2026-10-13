#!/usr/bin/env python3
"""Build reviewed Klipper purge macros locally; Python 3.10+, stdlib only.

Copyright 2026 Cong Duong / IDcrazy123. MIT.
No printer/network I/O. Photos document the original machine macro, not this revision.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
import zipfile

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent


class ProfileError(ValueError):
    pass


def keys(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required.split()):
        raise ProfileError(f"{label}: expected exactly {required}")


def number(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ProfileError(f"{label}: finite number required")
    if not minimum <= value <= maximum:
        raise ProfileError(f"{label}: expected {minimum}..{maximum}")
    return float(value)


def validate(profile, require_reviewed=True):
    p = copy.deepcopy(profile)
    keys(p, "schema reviewed axis purge_area line_length line_gap edge_margin passes pass_spacing prime_z travel_z wipe_distance purge_cross_section print_speed travel_speed z_speed retract_speed tools", "profile")
    if type(p["schema"]) is not int or p["schema"] != 1:
        raise ProfileError("schema: expected integer 1")
    if type(p["reviewed"]) is not bool or (require_reviewed and not p["reviewed"]):
        raise ProfileError("review your actual printer profile before building")
    if p["axis"] not in ("x", "y"):
        raise ProfileError("axis: expected x or y")
    keys(p["purge_area"], "x_min x_max y_min y_max", "purge_area")
    a = p["purge_area"]
    for k in a:
        number(a[k], k, -1000, 2000)
    if a["x_min"] >= a["x_max"] or a["y_min"] >= a["y_max"]:
        raise ProfileError("purge_area: reversed or empty rectangle")
    for k, lo, hi in [("line_length", 5, 500), ("line_gap", 0.5, 100),
                      ("edge_margin", 0.5, 50), ("pass_spacing", 0.2, 20),
                      ("prime_z", 0.1, 1), ("travel_z", 1, 100),
                      ("wipe_distance", 0, 30), ("purge_cross_section", 0.01, 5),
                      ("print_speed", 1, 100), ("travel_speed", 1, 300),
                      ("z_speed", 0.1, 20), ("retract_speed", 0.1, 100)]:
        number(p[k], k, lo, hi)
    if type(p["passes"]) is not int or not 1 <= p["passes"] <= 6:
        raise ProfileError("passes: integer 1..6 required")
    if p["travel_z"] <= p["prime_z"]:
        raise ProfileError("travel_z must exceed prime_z")
    if p["edge_margin"] < p["purge_cross_section"] / p["prime_z"] / 2:
        raise ProfileError("edge_margin too small for nominal purge bead")
    if p["pass_spacing"] < p["purge_cross_section"] / p["prime_z"]:
        raise ProfileError("pass_spacing: nominal purge beads overlap")
    if not isinstance(p["tools"], list) or not 1 <= len(p["tools"]) <= 32:
        raise ProfileError("tools: 1..32 mappings required")
    ids, extruders = set(), set()
    for t in p["tools"]:
        keys(t, "id extruder select_command nozzle_diameter filament_diameter max_cross_section max_volume_rate entry_recovery parked_retract initial_retract standby_temp", "tool")
        if type(t["id"]) is not int or not 0 <= t["id"] <= 999 or t["id"] in ids:
            raise ProfileError("tool ID must be unique integer 0..999")
        ids.add(t["id"])
        if not isinstance(t["extruder"], str) or not re.fullmatch(r"extruder[0-9]*", t["extruder"]) or t["extruder"] in extruders:
            raise ProfileError("unique standard extruder names required")
        extruders.add(t["extruder"])
        # One reviewed select command, never arbitrary multi-line G-code/Jinja.
        cmd = t["select_command"]
        if not isinstance(cmd, str) or not re.fullmatch(r"(?:T[0-9]+|[A-Z_]+(?: [A-Z_]+=[A-Za-z0-9_.-]+)*)", cmd):
            raise ProfileError("select_command: one plain tool-selection command required")
        if cmd.split()[0] in {"GCODE_MACRO", "SET_GCODE_OFFSET", "FORCE_MOVE", "SAVE_CONFIG", "RESTART", "FIRMWARE_RESTART"}:
            raise ProfileError("select_command: not a tool selector")
        if re.fullmatch(r"T[0-9]+", cmd) and cmd != f"T{t['id']}":
            raise ProfileError("select_command Tn does not match tool ID")
        for k, lo, hi in [("nozzle_diameter", 0.15, 1.5), ("filament_diameter", 1, 3.5),
                          ("max_cross_section", 0.01, 10), ("max_volume_rate", 0.1, 100),
                          ("entry_recovery", 0, 20), ("parked_retract", 0, 20),
                          ("initial_retract", 0, 20), ("standby_temp", 0, 300)]:
            number(t[k], k, lo, hi)
        if p["purge_cross_section"] > t["max_cross_section"]:
            raise ProfileError("purge exceeds tool max_cross_section")
        if p["purge_cross_section"] * p["print_speed"] > t["max_volume_rate"]:
            raise ProfileError("purge exceeds tool max_volume_rate")
    layout(p)  # Reject geometry before any output exists.
    return p


def layout(p):
    a, axis = p["purge_area"], p["axis"]
    cross = "y" if axis == "x" else "x"
    n = len(p["tools"])
    span = a[axis + "_max"] - a[axis + "_min"] - 2 * p["edge_margin"]
    slot = (span - (n - 1) * p["line_gap"]) / n
    length = min(p["line_length"], slot - 2 * p["wipe_distance"])
    cross_span = a[cross + "_max"] - a[cross + "_min"] - 2 * p["edge_margin"]
    if length < 5 or cross_span < (p["passes"] - 1) * p["pass_spacing"]:
        raise ProfileError("purge area cannot fit strokes, passes and reserved wipes")
    result = []
    for i, tool in enumerate(sorted(p["tools"], key=lambda t: t["id"])):
        start = a[axis + "_min"] + p["edge_margin"] + i * (slot + p["line_gap"]) + p["wipe_distance"]
        base = a[cross + "_min"] + p["edge_margin"]
        points = []
        for row in range(p["passes"]):
            c = base + row * p["pass_spacing"]
            stroke = [[start, c], [start + length, c]]
            if axis == "y":
                stroke = [[q[1], q[0]] for q in stroke]
            if row % 2:
                stroke.reverse()
            points.append(stroke)
        wipe = points[-1][-1].copy()
        wipe[0 if axis == "x" else 1] += p["wipe_distance"] * (1 if p["passes"] % 2 else -1)
        e = length * p["purge_cross_section"] / (math.pi * tool["filament_diameter"] ** 2 / 4)
        result.append(dict(tool, strokes=points, wipe=wipe, stroke_length=length, e_per_stroke=e))
    return result


def make_cfg(p):
    runtime = dict(p, tools=layout(p))
    header = (f"# Toolchanger Purge Lines {VERSION}; MIT; Cong Duong / IDcrazy123\n"
              "# Generated locally. No homing, mesh/probe, offset saving or printer start/end here.\n"
              "# Entry: PRIME_LINES INITIAL_TOOL=n Tn_TEMP=...; only listed positive-temperature tools run.\n"
              "# Exit: initial tool mounted, G90/M83/E0, at travel_z with initial_retract still applied.\n"
              "# Caller/slicer owns matching recovery. See README.md before installation.\n"
              "[gcode_macro _TC_PURGE_CONFIG]\n"
              f"variable_profile: {runtime!r}\n"
              "gcode:\n    {action_respond_info(\"Toolchanger Purge Lines config loaded\")}\n\n")
    return header + (ROOT / "templates/macros.jinja").read_text(encoding="utf-8")


def make_svg(p):
    a = p["purge_area"]
    w, h = a["x_max"] - a["x_min"], a["y_max"] - a["y_min"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{a["x_min"]-4} {-a["y_max"]-4} {w+8} {h+8}">',
             f'<rect x="{a["x_min"]}" y="{-a["y_max"]}" width="{w}" height="{h}" fill="#eee" stroke="#555" stroke-width="0.2"/>']
    for t in layout(p):
        color = ["#d53e4f", "#3288bd", "#444", "#9e9d24", "#884ea0"][t["id"] % 5]
        for start, end in t["strokes"]:
            parts.append(f'<path d="M{start[0]},{-start[1]} L{end[0]},{-end[1]}" stroke="{color}" stroke-width="{p["purge_cross_section"]/p["prime_z"]}" fill="none"/>')
        end, wipe = t["strokes"][-1][-1], t["wipe"]
        parts.append(f'<path d="M{end[0]},{-end[1]} L{wipe[0]},{-wipe[1]}" stroke="{color}" stroke-width="0.3" stroke-dasharray="1 1"/>')
        start = t["strokes"][0][0]
        parts.append(f'<text x="{start[0]}" y="{-start[1]+3}" font-size="2">{html.escape("T"+str(t["id"]))}</text>')
    return "\n".join(parts + ["</svg>"])


def build(p, out):
    p = validate(p)
    out = Path(out)
    targets = [out, out.with_suffix(".svg"), out.with_suffix(".report.json")]
    if any(f.exists() for f in targets):
        raise ProfileError("output exists; use a new filename")
    cfg = make_cfg(p)
    report = dict(version=VERSION, cfg_sha256=hashlib.sha256(cfg.encode()).hexdigest(),
                  tools=layout(p), exit_state="G90/M83/E0; initial tool at travel_z, still retracted", hardware="community revision not physically validated")
    out.parent.mkdir(parents=True, exist_ok=True)
    for path, data in zip(targets, [cfg, make_svg(p), json.dumps(report, indent=2)]):
        with path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(data)
    return report


def package(out):
    paths = [ROOT / n for n in ["build_purge.py", "README.md", "README.vi.md", "CHANGELOG.md", "LICENSE", "AGENTS.md", "profiles/printer.example.json", "templates/macros.jinja", "templates/prime-lines.template.cfg"]]
    paths += sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "tests").glob("test_*.py")) + sorted((ROOT / "photos").glob("*.jpg"))
    if any(not p.is_file() for p in paths):
        raise ProfileError("release files missing")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        manifest = {}
        for path in paths:
            data = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            manifest[name] = hashlib.sha256(data).hexdigest()
            z.writestr(name, data)
        z.writestr("MANIFEST.sha256.json", json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description=f"Toolchanger Purge Lines {VERSION}: local builder, no printer access")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "build"):
        s = sub.add_parser(command)
        s.add_argument("--profile", required=True)
        if command == "build":
            s.add_argument("-o", "--output", required=True)
    s = sub.add_parser("package")
    s.add_argument("-o", "--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "package":
            package(args.output)
        else:
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ProfileError(f"duplicate JSON key: {key}")
                    result[key] = value
                return result
            p = json.loads(Path(args.profile).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                           parse_constant=lambda s: (_ for _ in ()).throw(ProfileError("nonfinite JSON")))
            if args.command == "build":
                print(json.dumps(build(p, args.output), indent=2))
            else:
                p = validate(p, require_reviewed=False)
                print(json.dumps(dict(valid=True, reviewed=p["reviewed"], tools=[t["id"] for t in p["tools"]])))
        return 0
    except (ProfileError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
