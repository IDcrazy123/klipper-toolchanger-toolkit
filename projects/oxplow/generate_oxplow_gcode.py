#!/usr/bin/env python3
"""Oxplow calibration toolkit: Python 3.10+, standard library only.

Klipper G-code and read-only Moonraker discovery. See docs/PROVENANCE.md.
Original attribution: Antigravity AI & Voron Community (MIT declared locally).
Oxplow idea: Maxim7745; Printables remix by Cong Duong (CongDuong_4017348).
Sources and page/header licensing declarations are recorded in PROVENANCE.md.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib import error, parse, request
import zipfile

VERSION = "2.3.2"
ROOT = Path(__file__).resolve().parent


class ProfileError(ValueError):
    """Invalid configuration or artifact."""


def number(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ProfileError(f"{name}: expected a finite number")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ProfileError(f"{name}: outside [{low}, {high}]")
    return float(value)


def keys(obj, required, optional=(), name="profile"):
    if not isinstance(obj, dict):
        raise ProfileError(f"{name}: expected an object")
    missing = set(required) - obj.keys()
    extra = obj.keys() - set(required) - set(optional)
    if missing or extra:
        raise ProfileError(f"{name}: missing={sorted(missing)}, unknown={sorted(extra)}")


def read_json(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ProfileError(f"Duplicate JSON key: {key}")
            obj[key] = value
        return obj
    with Path(path).open(encoding="utf-8-sig") as handle:
        return json.load(handle, object_pairs_hook=unique)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def check_commands(commands, name):
    if not isinstance(commands, list) or not commands:
        raise ProfileError(f"{name}: nonempty list of explicit G-code lines required")
    for line in commands:
        if not isinstance(line, str) or not line.strip() or "\n" in line or "\r" in line:
            raise ProfileError(f"{name}: each entry must be one nonempty line")
        code = line.split(";", 1)[0].strip()
        if not code:
            continue
        if any(s in code for s in ("||", "&&", ">", "<", "`", "$", "{", "}")):
            raise ProfileError(f"{name}: shell/Jinja syntax is not executable G-code")
        command = code.split()[0].upper()
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", command):
            raise ProfileError(f"{name}: invalid command: {command}")
        if command.startswith("REVIEW_"):
            raise ProfileError(f"{name}: replace placeholder {command} with the actual printer macro")
        if command in {"M500", "M420", "G29", "M84", "M18", "M112", "SAVE_CONFIG", "SET_KINEMATIC_POSITION",
                       "FORCE_MOVE", "RESTART", "FIRMWARE_RESTART", "SET_GCODE_OFFSET"}:
            raise ProfileError(f"{name}: unsupported calibration command {command}; review printer macros")


def extrusion_area(tool, height=None, width=None):
    h = tool["nominal_height"] if height is None else height
    w = tool["line_width"] if width is None else width
    return h * (w - h) + math.pi * h * h / 4


def annotation_area(tool):
    return extrusion_area(tool, tool["annotation_height"], tool["annotation_line_width"])


def normalize_profile(raw, runnable=False):
    p = copy.deepcopy(raw)
    keys(p, ("schema_version", "name", "reviewed", "machine", "start_gcode", "end_gcode", "test", "tools"), ("notes", "discovery"))
    if type(p["schema_version"]) is not int or p["schema_version"] != 1:
        raise ProfileError("schema_version must be 1")
    if not isinstance(p["name"], str) or not p["name"].strip() or any(c in p["name"] for c in "\r\n"):
        raise ProfileError("name must be a nonempty single line")
    if type(p["reviewed"]) is not bool:
        raise ProfileError("reviewed must be boolean")
    if runnable and not p["reviewed"]:
        raise ProfileError("Draft profile: review macros, tool mapping and safe region before setting reviewed=true")
    m = p["machine"]
    keys(m, ("safe_min", "safe_max", "z_min", "z_max", "travel_z", "toolchange_z", "bed_temp", "bed_max_temp"),
         ("max_velocity", "max_z_velocity"), "machine")
    for k in ("safe_min", "safe_max"):
        if not isinstance(m[k], list) or len(m[k]) != 2:
            raise ProfileError(f"machine.{k}: [X, Y] required")
        m[k] = [number(v, f"machine.{k}", -10000, 10000) for v in m[k]]
    if any(a >= b for a, b in zip(m["safe_min"], m["safe_max"])):
        raise ProfileError("safe_max must exceed safe_min on both axes")
    for k in ("z_min", "z_max", "travel_z", "toolchange_z"):
        m[k] = number(m[k], f"machine.{k}", -100, 10000)
    if not m["z_min"] < m["travel_z"] <= m["toolchange_z"] <= m["z_max"]:
        raise ProfileError("Require z_min < travel_z <= toolchange_z <= z_max")
    m["max_velocity"] = number(m.get("max_velocity", 100), "max_velocity", 1, 1000)
    m["max_z_velocity"] = number(m.get("max_z_velocity", 5), "max_z_velocity", .1, 100)
    m["bed_max_temp"] = number(m["bed_max_temp"], "bed_max_temp", 1, 200)
    m["bed_temp"] = number(m["bed_temp"], "bed_temp", 1, m["bed_max_temp"] - 1)
    check_commands(p["start_gcode"], "start_gcode")
    check_commands(p["end_gcode"], "end_gcode")
    test = p["test"]
    keys(test, (), ("lines", "patch_length", "gap", "direction", "print_speed", "travel_speed", "z_speed",
                    "retract_speed", "retract_length", "soak_seconds", "temperature_tolerance", "center",
                    "define_objects", "end_retract_owner", "end_lift_owner", "annotation_speed", "label_scale", "annotations"), "test")
    defaults = dict(lines=51, patch_length=20.0, gap=8.0, direction="high-to-low", print_speed=20.0,
                    travel_speed=100.0, z_speed=5.0, retract_speed=20.0, retract_length=0.6,
                    soak_seconds=0.0, temperature_tolerance=2.0, center=None, define_objects=False,
                    end_retract_owner="generator", end_lift_owner="generator", annotation_speed=10.0, label_scale=1.5, annotations=False)
    for k, v in defaults.items():
        test.setdefault(k, v)
    if type(test["define_objects"]) is not bool or test["end_retract_owner"] not in ("generator", "end_macro"):
        raise ProfileError("define_objects must be boolean; end_retract_owner is generator or end_macro")
    if type(test["annotations"]) is not bool:
        raise ProfileError("test.annotations must be boolean")
    if test["end_lift_owner"] not in ("generator", "end_macro"):
        raise ProfileError("end_lift_owner is generator or end_macro")
    if test["end_lift_owner"] == "end_macro" and test["end_retract_owner"] != "end_macro":
        raise ProfileError("end_lift_owner=end_macro requires end_retract_owner=end_macro; review end macro retract/lift contract")
    if type(test["lines"]) is not int or not 5 <= test["lines"] <= 1001 or test["lines"] % 2 == 0:
        raise ProfileError("test.lines must be odd, 5..1001")
    bounds = dict(patch_length=(5, 150), gap=(2, 100), label_scale=(1, 3), print_speed=(1, 100), annotation_speed=(1, 100), travel_speed=(1, 500),
                  z_speed=(.1, 30), retract_speed=(1, 100), retract_length=(0, 5), soak_seconds=(0, 3600), temperature_tolerance=(.5, 10))
    for k, limits in bounds.items():
        test[k] = number(test[k], f"test.{k}", *limits)
    if max(test["print_speed"], test["annotation_speed"], test["travel_speed"]) > m["max_velocity"] or test["z_speed"] > m["max_z_velocity"]:
        raise ProfileError("Test speeds exceed configured machine velocity limits")
    if m["bed_temp"] + test["temperature_tolerance"] >= m["bed_max_temp"]:
        raise ProfileError("Bed temperature tolerance reaches max_temp")
    if test["direction"] not in ("high-to-low", "low-to-high"):
        raise ProfileError("direction must be high-to-low or low-to-high")
    if test["center"] is not None:
        if not isinstance(test["center"], list) or len(test["center"]) != 2:
            raise ProfileError("center must be null or [X, Y]")
        test["center"] = [number(v, "center", -10000, 10000) for v in test["center"]]
    if not isinstance(p["tools"], list) or not 1 <= len(p["tools"]) <= 16:
        raise ProfileError("tools must contain 1..16 tools")
    ids, extruders = set(), set()
    for t in p["tools"]:
        keys(t, ("id", "extruder", "select_gcode", "nozzle_diameter", "filament_diameter", "temperature", "min_extrude_temp", "max_temp"),
             ("nominal_height", "ramp_range", "line_width", "line_step", "max_volumetric_flow", "max_extrude_cross_section",
              "max_extrude_only_distance", "max_extrude_only_velocity", "material", "initial_retract", "temperature_command",
              "annotation_height", "annotation_line_width", "annotation_z_adjust", "test_z_adjust", "saved_tool_z_offset"), "tool")
        if type(t["id"]) is not int or not 0 <= t["id"] <= 999 or t["id"] in ids:
            raise ProfileError("Tool IDs must be unique integers, 0..999")
        ids.add(t["id"])
        ext = t["extruder"]
        if not isinstance(ext, str) or not re.fullmatch(r"extruder\d*", ext) or ext in extruders:
            raise ProfileError("Extruder names must be unique Klipper extruder names")
        extruders.add(ext)
        t["initial_retract"] = number(t.get("initial_retract", 0), "initial_retract", 0, 50)
        t.setdefault("temperature_command", "named-heater")
        if t["temperature_command"] not in ("named-heater", "toolchanger"):
            raise ProfileError("temperature_command must be named-heater or toolchanger")
        if not isinstance(t["select_gcode"], str):
            raise ProfileError("select_gcode must be a string")
        if t["select_gcode"]:
            check_commands([t["select_gcode"]], "select_gcode")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?: [A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_.+-]+)*", t["select_gcode"]):
                raise ProfileError("select_gcode must be a macro call with named parameters")
        elif len(p["tools"]) != 1 or t["id"] != 0 or ext != "extruder":
            raise ProfileError("Only single-tool T0/extruder may omit selection")
        d = t["nozzle_diameter"] = number(t["nozzle_diameter"], "nozzle_diameter", .15, 1.2)
        t["filament_diameter"] = number(t["filament_diameter"], "filament_diameter", 1, 3.5)
        t["min_extrude_temp"] = number(t["min_extrude_temp"], "min_extrude_temp", 1, 400)
        t["max_temp"] = number(t["max_temp"], "max_temp", t["min_extrude_temp"] + 2, 500)
        t["temperature"] = number(t["temperature"], "temperature", t["min_extrude_temp"] + test["temperature_tolerance"] + 1,
                                    t["max_temp"] - test["temperature_tolerance"] - 1)
        h = t["nominal_height"] = number(t.get("nominal_height", d * .6), "nominal_height", .05, d * .8)
        r = t["ramp_range"] = number(t.get("ramp_range", h * .25), "ramp_range", 0, h - .05)
        t["annotation_height"] = number(t.get("annotation_height", min(h, d * .5)), "annotation_height", .05, d * .8)
        for k in ("annotation_z_adjust", "test_z_adjust"):
            t[k] = number(t.get(k, 0), k, -1, 1)
        t.setdefault("saved_tool_z_offset", None)
        if t["saved_tool_z_offset"] is not None:
            t["saved_tool_z_offset"] = number(t["saved_tool_z_offset"], "saved_tool_z_offset", -20, 20)
        t["line_width"] = number(t.get("line_width", d * 1.1), "line_width", h, d * 2)
        t["annotation_line_width"] = number(t.get("annotation_line_width", d * 1.5), "annotation_line_width", t["annotation_height"], d * 2)
        # Match nominal area per bed width: h * spacing == rounded-rectangle bead area.
        # Using nozzle diameter alone would bias nominal coverage when h/width differ.
        t["line_step"] = number(t.get("line_step", extrusion_area(t) / h), "line_step", d * .5, t["line_width"])
        if r and 2 * r / (test["lines"] - 1) < .0001:
            raise ProfileError("Z increment below output precision (0.0001 mm)")
        ramp_low, ramp_high = h + t["test_z_adjust"] - r, h + t["test_z_adjust"] + r
        annotation_z = t["annotation_height"] + t["annotation_z_adjust"]
        if ramp_low < max(.05, m["z_min"]) or ramp_high > d or ramp_high >= m["travel_z"]:
            raise ProfileError("Z ramp must stay above z_min/0.05, below nozzle diameter and travel_z")
        if not max(.05, m["z_min"]) <= annotation_z <= d or annotation_z >= m["travel_z"]:
            raise ProfileError("Annotation Z must stay above z_min/0.05, below nozzle diameter and travel_z")
        for k, default, limits in (("max_volumetric_flow", 8.0, (.1, 100)), ("max_extrude_cross_section", 4 * d * d, (.001, 100)),
                                   ("max_extrude_only_distance", 50.0, (.001, 1000)), ("max_extrude_only_velocity", 100.0, (.1, 1000))):
            t[k] = number(t.get(k, default), k, *limits)
        area = max(extrusion_area(t), annotation_area(t)) if test["annotations"] else extrusion_area(t)
        flow = extrusion_area(t) * test["print_speed"]
        if test["annotations"]:
            flow = max(flow, annotation_area(t) * test["annotation_speed"])
        if area > t["max_extrude_cross_section"] or flow > t["max_volumetric_flow"]:
            raise ProfileError(f"T{t['id']}: extrusion cross section or volumetric flow exceeds limit")
        if max(test["retract_length"], t["initial_retract"]) > t["max_extrude_only_distance"] or test["retract_speed"] > t["max_extrude_only_velocity"]:
            raise ProfileError("Retraction exceeds configured distance/velocity")
    return p


def row_z(tool, test, index):
    sign = 1 if test["direction"] == "low-to-high" else -1
    return tool["nominal_height"] + tool["test_z_adjust"] + sign * tool["ramp_range"] * (2 * index / (test["lines"] - 1) - 1)


FONT = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgecd", "7": "abc", "8": "abcdefg", "9": "abfgcd"}
SEGMENTS = {"a": ((0, 1), (1, 1)), "b": ((1, 1), (1, .5)), "c": ((1, .5), (1, 0)), "d": ((1, 0), (0, 0)),
            "e": ((0, 0), (0, .5)), "f": ((0, .5), (0, 1)), "g": ((0, .5), (1, .5))}


def generate_char_strokes(char, x0, y0, w, h):
    # Same seven-segment glyphs, ordered as connected trails. Avoid stopping
    # extrusion and lifting/retracting at every vertex of a digit.
    vertices = {"A": (0, 1), "B": (1, 1), "C": (1, .5),
                "D": (1, 0), "E": (0, 0), "F": (0, .5)}
    paths = {"0": ("ABCDEFA",), "1": ("BCD",), "2": ("ABCFED",),
             "3": ("ABCF", "CDE"), "4": ("AFCB", "CD"),
             "5": ("BAFCDE",), "6": ("BAFEDCF",), "7": ("ABCD",),
             "8": ("CBAFCDEF",), "9": ("FABCF", "CDE")}
    strokes = ([((.5, 0), (.5, 1)), ((0, 1), (1, 1))] if char == "T" else
               [(vertices[a], vertices[b]) for path in paths.get(char, ()) for a, b in zip(path, path[1:])])
    return [[(x0 + x * w, y0 + y * h) for x, y in stroke] for stroke in strokes]


def short_label_travel(previous, segment):
    """Only local travel between label strokes, never across a patch or tick."""
    return (previous is not None and previous["kind"] == segment["kind"] == "label"
            and previous["end_z"] == segment["z"]
            and math.dist(previous["b"], segment["a"]) <= 5)


def layout(p):
    m, test = p["machine"], p["test"]
    length = test["patch_length"]
    scale = test["label_scale"]
    # Print order remains the explicit macro/retraction contract in tools[].
    # Physical left-to-right identification is numeric tool ID in patch-only mode.
    spatial_tools = p["tools"] if test["annotations"] else sorted(p["tools"], key=lambda t: t["id"])
    widths = ([max(length + 14, (len(str(t["id"])) + 1) * 4.5 * scale + 10) for t in spatial_tools]
              if test["annotations"] else [length for t in spatial_tools])
    heights = [(test["lines"] - 1) * t["line_step"] for t in p["tools"]]
    width = sum(widths) + test["gap"] * (len(widths) - 1)
    label_band = 5 * scale + 5 if test["annotations"] else 0
    height = max(max(heights), 18) + label_band if test["annotations"] else max(heights)
    center = test["center"] or [(a + b) / 2 for a, b in zip(m["safe_min"], m["safe_max"])]
    left, bottom = center[0] - width / 2, center[1] - height / 2
    cells = []
    for tool, cell_width in zip(spatial_tools, widths):
        cells.append(dict(tool=tool, x=left + (8 if test["annotations"] else 0),
                          y=bottom + label_band - 1 if test["annotations"] else bottom,
                          height=(test["lines"] - 1) * tool["line_step"]))
        left += cell_width + test["gap"]
    by_id = {c["tool"]["id"]: c for c in cells}
    cells = [by_id[t["id"]] for t in p["tools"]]
    segments = []

    def add(cell, a, b, z, kind, index=None, end_z=None):
        t = cell["tool"]
        segments.append(dict(tool=t["id"], a=list(a), b=list(b), z=z, end_z=z if end_z is None else end_z,
                             kind=kind, row=index, width=t["line_width"] if kind in ("row", "connector") else t["annotation_line_width"],
                             extrusion_height=t["nominal_height"] if kind in ("row", "connector") else t["annotation_height"]))
    for cell in cells:
        t, x, y = cell["tool"], cell["x"], cell["y"]
        # Saved tool/probe offsets are already part of the printer's coordinate transform.
        # Never add saved_tool_z_offset here; that would apply the correction twice.
        h = t["annotation_height"] + t["annotation_z_adjust"]
        if test["annotations"]:
            add(cell, (x - 8, y), (x - 8, y + 18), h, "purge")
            label = f"T{t['id']}"
            lx = x + (length - ((len(label) - 1) * 4.5 + 3) * scale) / 2
            label_y = y - 2.5 - 5 * scale
            first = (lx + 1.5 * scale, label_y)
            add(cell, (first[0] - 4, first[1]), first, h, "lead_in")
            for i, char in enumerate(label):
                for a, b in generate_char_strokes(char, lx + i * 4.5 * scale, label_y, 3 * scale, 5 * scale):
                    add(cell, a, b, h, "label")
            for i in (0, (test["lines"] - 1) // 4, (test["lines"] - 1) // 2, 3 * (test["lines"] - 1) // 4, test["lines"] - 1):
                ty = y + i * t["line_step"]
                center_tick = i == (test["lines"] - 1) // 2
                tick_w = 4 if center_tick else 2.5
                add(cell, (x - 2 - tick_w, ty), (x - 2, ty), h, "tick")
                if center_tick:
                    add(cell, (x + length + 2, ty), (x + length + 6, ty), h, "tick")
        for i in range(test["lines"]):
            ty, z = y + i * t["line_step"], row_z(t, test, i)
            a, b = (x, ty), (x + length, ty)
            if i % 2:
                a, b = b, a
            add(cell, a, b, z, "row", i)
            if i < test["lines"] - 1:
                add(cell, b, (b[0], ty + t["line_step"]), z, "connector", end_z=row_z(t, test, i + 1))
    for s in segments:
        radius = s["width"] / 2
        for point in (s["a"], s["b"]):
            if any(v - radius < lo or v + radius > hi for v, lo, hi in zip(point, m["safe_min"], m["safe_max"])):
                raise ProfileError(f"T{s['tool']} {s['kind']} footprint exceeds safe XY at {point}")
    return cells, segments


def check_call(t, p, stage):
    reference = "" if t["saved_tool_z_offset"] is None else f" TOOL={t['id']} SAVED_Z={t['saved_tool_z_offset']:.6f}"
    return (f"_OXPLOW_CHECK VERSION={VERSION} STAGE={stage} EXTRUDER={t['extruder']} NOZZLE={t['nozzle_diameter']:.4f} "
            f"FILAMENT={t['filament_diameter']:.4f} TEMP={t['temperature']:g} BED={p['machine']['bed_temp']:g} "
            f"AREA={(max(extrusion_area(t), annotation_area(t)) if p['test']['annotations'] else extrusion_area(t)):.6f} RETRACT={max(p['test']['retract_length'], t['initial_retract']):g} LIFT={p['machine']['toolchange_z']:g} "
            f"TOL={p['test']['temperature_tolerance']:g} RSPEED={p['test']['retract_speed']:g} "
            f"SPEED={max(p['test']['print_speed'], p['test']['annotation_speed'], p['test']['travel_speed']):g} ZSPEED={p['test']['z_speed']:g}{reference}")


def temperature_line(tool, target):
    if tool["temperature_command"] == "toolchanger":
        return f"SET_TOOL_TEMPERATURE T={tool['id']} TARGET={target:g}"
    return f"SET_HEATER_TEMPERATURE HEATER={tool['extruder']} TARGET={target:g}"


def object_definitions(p, segments):
    if not p["test"]["define_objects"]:
        return []
    lines = ["EXCLUDE_OBJECT_DEFINE RESET=1"]
    for t in p["tools"]:
        strokes = [s for s in segments if s["tool"] == t["id"]]
        xmin, ymin = [math.floor(min(v[i] - s["width"] / 2 for s in strokes for v in (s["a"], s["b"])) * 1000) / 1000 for i in (0, 1)]
        xmax, ymax = [math.ceil(max(v[i] + s["width"] / 2 for s in strokes for v in (s["a"], s["b"])) * 1000) / 1000 for i in (0, 1)]
        polygon = canonical([[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]])
        lines.append(f"EXCLUDE_OBJECT_DEFINE NAME=OXPLOW_T{t['id']} CENTER={canonical([(xmin+xmax)/2, (ymin+ymax)/2])} POLYGON={polygon}")
    return lines


def generate_oxplow_gcode(profile):
    """Generate reviewed Klipper G-code. The v1 preset API was retired."""
    p = normalize_profile(profile, runnable=True)
    cells, segments = layout(p)
    test, m = p["test"], p["machine"]
    out = [f"; OXPLOW {VERSION} / Klipper ONLY", f"; Profile: {p['name']}", f"; Profile SHA256: {digest(p)}",
           f"; REQUIRED: install/include oxplow_runtime.cfg {VERSION}; see docs/INSTALL_KLIPPER.md.",
           "; Print as a virtual-SD file. Do not paste/stream commands individually.",
           f"; Direction: {test['direction']}; row 0 is LOWEST Y, not necessarily lowest Z.",
           "; Left-to-right (+X): " + " -> ".join(f"T{c['tool']['id']}" for c in sorted(cells, key=lambda c: c['x'])),
           f"; Printed annotations: {test['annotations']}; startup macro may have its own purge.",
           "; Constant nominal extrusion across ramp. Runtime correction = Z_best - nominal_height.",
           "; Positive Klipper Z_ADJUST raises nozzle. No automatic offset/config saving.",
           "; Static checks cannot certify collision-free macro or hardware motion.",
           "SET_GCODE_VARIABLE MACRO=_OXPLOW_CHECK VARIABLE=preflight_token VALUE=1"]
    for t in p["tools"]:
        out.append(check_call(t, p, "config"))
    out.extend(object_definitions(p, segments))
    out.extend(["; BEGIN USER START", *p["start_gcode"], "; END USER START", "G90", "M83", "M220 S100", "M221 S100",
                check_call(p["tools"][0], p, "ready"), f"SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={m['bed_temp']:g}",
                f"TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM={m['bed_temp'] - test['temperature_tolerance']:g} MAXIMUM={m['bed_temp'] + test['temperature_tolerance']:g}"])
    if test["soak_seconds"]:
        out.append(f"G4 P{test['soak_seconds'] * 1000:.0f}")
    tf, pf, zf, rf = [test[k] * 60 for k in ("travel_speed", "print_speed", "z_speed", "retract_speed")]
    r = test["retract_length"]
    for tool_index, cell in enumerate(cells):
        t = cell["tool"]
        out.extend([f"; BEGIN TOOL T{t['id']}", "G90", "M83", f"G0 Z{m['toolchange_z']:.4f} F{zf:g}"])
        out.append(f"; Test adjustment={t['test_z_adjust']:+.4f}; saved tool offset is NOT added to G-code Z")
        if test["annotations"]:
            out.append(f"; Annotation Z={t['annotation_height'] + t['annotation_z_adjust']:.4f}")
        # Pickup hooks can wait on the parked tool's target. Set it before selection.
        out.append(temperature_line(t, t["temperature"]))
        if t["select_gcode"]:
            out.append(t["select_gcode"])
        out.extend(["G90", "M83", "M220 S100", "M221 S100", check_call(t, p, "selected"),
                    temperature_line(t, t["temperature"]),
                    f"TEMPERATURE_WAIT SENSOR={t['extruder']} MINIMUM={t['temperature'] - test['temperature_tolerance']:g} MAXIMUM={t['temperature'] + test['temperature_tolerance']:g}",
                    check_call(t, p, "print")])
        tool_segments = [s for s in segments if s["tool"] == t["id"]]
        retracted, previous = False, None
        for s in tool_segments:
            # The same row endpoint can differ by binary float roundoff when
            # calculated as y+i*step versus y+(i-1)*step+step. Do not retract
            # between coordinates that are identical well below output precision.
            continuous = (previous is not None and math.dist(previous["b"], s["a"]) <= 1e-8
                          and abs(previous["end_z"] - s["z"]) <= 1e-8
                          and (s["kind"] == "label" and previous["kind"] in ("label", "lead_in") or
                               s["kind"] in ("row", "connector") and previous["kind"] in ("row", "connector")))
            local_label = short_label_travel(previous, s)
            if local_label and not continuous:
                out.append(f"G0 X{s['a'][0]:.4f} Y{s['a'][1]:.4f} F{test['annotation_speed'] * 60:g} ; short label travel, no retract/lift")
            elif not continuous:
                if previous is not None and r and not retracted:
                    out.append(f"G1 E-{r:.5f} F{rf:g}")
                    retracted = True
                lift = m["toolchange_z"] if previous is None else m["travel_z"]
                out.extend([f"G0 Z{lift:.4f} F{zf:g}", f"G0 X{s['a'][0]:.4f} Y{s['a'][1]:.4f} F{tf:g}", f"G0 Z{s['z']:.4f} F{zf:g}"])
                if previous is None and t["initial_retract"]:
                    out.append(f"G1 E{t['initial_retract']:.5f} F{rf:g} ; recover known start-macro retract")
                if retracted:
                    out.append(f"G1 E{r:.5f} F{rf:g}")
                    retracted = False
            if s["kind"] == "row":
                delta = s["z"] - t["nominal_height"]
                out.append(f"; ROW T{t['id']} INDEX={s['row']} Y={s['a'][1]:.4f} Z={s['z']:.4f} DELTA={delta:+.4f}")
            else:
                out.append(f"; {s['kind']} Z={s['z']:.4f}")
            distance = math.dist(s["a"], s["b"])
            coefficient = extrusion_area(t, s["extrusion_height"], s["width"]) / (math.pi * (t["filament_diameter"] / 2) ** 2)
            feed = pf if s["kind"] in ("row", "connector") else test["annotation_speed"] * 60
            out.append(f"G1 X{s['b'][0]:.4f} Y{s['b'][1]:.4f} Z{s['end_z']:.4f} E{distance * coefficient:.5f} F{feed:g}")
            previous = s
        end_owns_retract = tool_index == len(cells) - 1 and test["end_retract_owner"] == "end_macro"
        if r and not end_owns_retract:
            out.append(f"G1 E-{r:.5f} F{rf:g}")
        end_owns_lift = tool_index == len(cells) - 1 and test["end_lift_owner"] == "end_macro"
        if end_owns_lift:
            out.append("; Final retract/lift handed to reviewed end macro at last printed Z")
        else:
            out.append(f"G0 Z{m['toolchange_z']:.4f} F{zf:g}")
        if not end_owns_retract:
            out.append(temperature_line(t, 0))
        out.append(f"; END TOOL T{t['id']}")
    out.extend(["; BEGIN USER END", *p["end_gcode"], "; END USER END", "TURN_OFF_HEATERS", "; END OXPLOW"])
    return "\n".join(out) + "\n"


def audit_gcode(gcode, profile):
    """Walk toolkit motion independently. Macro bodies and transforms remain opaque."""
    p = normalize_profile(profile)
    m, test = p["machine"], p["test"]
    by_id = {t["id"]: t for t in p["tools"]}
    _, geometry = layout(p)
    label_travels = set()
    for t in p["tools"]:
        strokes = [s for s in geometry if s["tool"] == t["id"]]
        for previous, s in zip(strokes, strokes[1:]):
            if short_label_travel(previous, s):
                label_travels.add((t["id"], *(round(v, 4) for v in (*previous["b"], *s["a"], s["z"]))))
    x = y = z = current_tool = feed = None
    absolute = relative_e = False
    phase = None
    count, rows, pending_row, pending_annotation = 0, {}, None, None
    last_printed_kind = None
    first_command = next((line.strip() for line in gcode.splitlines() if line.strip() and not line.lstrip().startswith(";")), "")
    if first_command != "SET_GCODE_VARIABLE MACRO=_OXPLOW_CHECK VARIABLE=preflight_token VALUE=1":
        raise ProfileError("Missing native runtime-install preflight before start/motion")
    for lineno, line in enumerate(gcode.splitlines(), 1):
        if line.startswith("; BEGIN USER"):
            phase = "user"
            continue
        if line.startswith("; END USER"):
            phase = None
            x = y = z = None
            feed = None
            absolute = relative_e = False
            continue
        match = re.fullmatch(r"; BEGIN TOOL T(\d+)", line)
        if match:
            current_tool = int(match[1])
            if current_tool not in by_id or current_tool in rows:
                raise ProfileError("Unexpected or duplicate tool body")
            rows[current_tool] = []
        row = re.fullmatch(r"; ROW T(\d+) INDEX=(\d+) Y=([-+\d.]+) Z=([-+\d.]+) DELTA=([-+\d.]+)", line)
        if row:
            if int(row[1]) != current_tool:
                raise ProfileError("Row/tool mismatch")
            pending_row = (int(row[2]), float(row[3]), float(row[4]))
        if re.fullmatch(r"; (purge|label|tick|lead_in) Z=[-+\d.]+", line):
            pending_annotation = float(line.split("Z=")[1])
            line_kind = line.split()[1]
        if phase == "user":
            continue
        code = line.split(";", 1)[0].strip()
        if not code:
            continue
        parts = code.split()
        cmd = parts[0]
        if cmd == "G90":
            absolute = True
        elif cmd == "M83":
            relative_e = True
        elif cmd in ("G91", "M82", "G92", "SET_GCODE_OFFSET"):
            raise ProfileError(f"line {lineno}: unexpected state mutation")
        if cmd not in ("G0", "G1"):
            continue
        if current_tool is None or not absolute or not relative_e:
            raise ProfileError(f"line {lineno}: motion without known tool/G90/M83")
        values = {}
        for part in parts[1:]:
            if not re.fullmatch(r"[XYZEF][-+]?\d+(?:\.\d+)?", part) or part[0] in values:
                raise ProfileError(f"line {lineno}: invalid/duplicate motion parameter")
            values[part[0]] = float(part[1:])
        nx, ny, nz = values.get("X", x), values.get("Y", y), values.get("Z", z)
        if nz is None or not m["z_min"] <= nz <= m["z_max"]:
            raise ProfileError(f"line {lineno}: Z outside range")
        xy, extrusion = "X" in values or "Y" in values, values.get("E", 0)
        feed = values.get("F", feed)
        if feed is None or feed <= 0:
            raise ProfileError(f"line {lineno}: positive feed rate required")
        speed = feed / 60
        if xy and speed > m["max_velocity"] + 1e-8:
            raise ProfileError(f"line {lineno}: XY velocity exceeds machine limit")
        if not xy and "Z" in values and speed > m["max_z_velocity"] + 1e-8:
            raise ProfileError(f"line {lineno}: Z velocity exceeds machine limit")
        if not xy and extrusion and speed > by_id[current_tool]["max_extrude_only_velocity"] + 1e-8:
            raise ProfileError(f"line {lineno}: extrude-only velocity exceeds tool limit")
        if xy:
            if nx is None or ny is None:
                raise ProfileError("Incomplete XY position")
            if not all(lo <= v <= hi for v, lo, hi in zip((nx, ny), m["safe_min"], m["safe_max"])):
                raise ProfileError(f"line {lineno}: XY outside safe region")
            if None not in (x, y, z):
                path_length = math.dist((x, y, z), (nx, ny, nz))
                if path_length and speed * abs(nz - z) / path_length > m["max_z_velocity"] + 1e-8:
                    raise ProfileError(f"line {lineno}: mixed-move Z velocity exceeds machine limit")
            if extrusion <= 0 and (z is None or min(z, nz) < m["travel_z"] - .0001):
                allowed_label = (cmd == "G0" and extrusion == 0 and last_printed_kind == "label"
                                 and z == nz and pending_annotation is None and pending_row is None
                                 and (current_tool, x, y, nx, ny, nz) in label_travels
                                 and values.get("F", 0) == test["annotation_speed"] * 60)
                if not allowed_label:
                    raise ProfileError(f"line {lineno}: unlifted XY travel")
                last_printed_kind = None
            if extrusion > 0:
                if x is None or y is None:
                    raise ProfileError("Extrusion starts without XY position")
                distance = math.dist((x, y), (nx, ny))
                tool = by_id[current_tool]
                area = extrusion * math.pi * (tool["filament_diameter"] / 2) ** 2 / max(distance, 1e-12)
                if area > tool["max_extrude_cross_section"] + .001:
                    raise ProfileError("G-code cross section exceeds limit")
                if speed * area > tool["max_volumetric_flow"] + .001:
                    raise ProfileError("G-code exceeds volumetric flow")
                expected_area = annotation_area(tool) if pending_annotation is not None else extrusion_area(tool)
                filament_area = math.pi * (tool["filament_diameter"] / 2) ** 2
                expected_e = distance * expected_area / filament_area
                # Account for rounded XY endpoints (4 decimals) and E (5).
                # Tiny connector moves must not fail just because of quantization.
                e_tolerance = math.sqrt(2) * .0001 * expected_area / filament_area + .00000501
                if pending_annotation is None and abs(extrusion - expected_e) > e_tolerance:
                    raise ProfileError("G-code extrusion differs from profile nominal area")
        elif abs(extrusion) > by_id[current_tool]["max_extrude_only_distance"]:
            raise ProfileError("G-code exceeds extrude-only distance")
        if pending_annotation is not None:
            tool = by_id[current_tool]
            expected_z = tool["annotation_height"] + tool["annotation_z_adjust"]
            if not xy or extrusion <= 0 or abs(nz - pending_annotation) > .0001 or abs(nz - expected_z) > .00011:
                raise ProfileError("Annotation Z differs from independent baseline height")
            expected_area = annotation_area(tool)
            if abs(area - expected_area) > .0001:
                raise ProfileError("Annotation extrusion differs from annotation height")
            pending_annotation = None
            last_printed_kind = line_kind
        if pending_row is not None:
            last_printed_kind = "row"
            i, expected_y, expected_z = pending_row
            if not xy or extrusion <= 0 or abs(ny - expected_y) > .0001 or abs(nz - expected_z) > .0001:
                raise ProfileError("Row metadata differs from extrusion move")
            if i != len(rows[current_tool]) or abs(nz - row_z(by_id[current_tool], test, i)) > .00011:
                raise ProfileError("Row order/Z differs from profile")
            rows[current_tool].append(i)
            pending_row = None
        x, y, z = nx, ny, nz
        count += 1
    if pending_row or pending_annotation is not None or set(rows) != set(by_id) or any(len(v) != test["lines"] for v in rows.values()):
        raise ProfileError("Missing tool or ramp rows")
    return dict(moves_checked=count, tools_checked=len(rows), rows_checked=sum(map(len, rows.values())),
                scope="Toolkit motion only; printer macros/transforms need hardware review")


def report_for(p, cells, segments, gcode=None):
    rows = []
    for cell in cells:
        t = cell["tool"]
        for i in range(p["test"]["lines"]):
            z = round(row_z(t, p["test"], i), 4)
            rows.append(dict(tool=t["id"], index=i, y=round(cell["y"] + i * t["line_step"], 4), z=z,
                             runtime_z_adjust=round(z - t["nominal_height"], 4)))
    result = dict(version=VERSION, profile_sha256=digest(p), profile=p, rows=rows,
                  annotations=[dict(tool=t["id"], z=t["annotation_height"] + t["annotation_z_adjust"],
                                    extrusion_height=t["annotation_height"], line_width=t["annotation_line_width"], saved_tool_z_offset=t["saved_tool_z_offset"],
                                    test_z_adjust=t["test_z_adjust"]) for t in p["tools"]] if p["test"]["annotations"] else [],
                  patches_left_to_right=[dict(tool=c["tool"]["id"], x_min=c["x"], x_max=c["x"] + p["test"]["patch_length"],
                                             y_first=c["y"], y_last=c["y"] + c["height"],
                                             z_first=row_z(c["tool"], p["test"], 0),
                                             z_last=row_z(c["tool"], p["test"], p["test"]["lines"] - 1))
                                        for c in sorted(cells, key=lambda c: c["x"])],
                  estimated_filament_mm=round(sum(math.dist(s["a"], s["b"]) * extrusion_area(c["tool"], s["extrusion_height"], s["width"]) /
                    (math.pi * (c["tool"]["filament_diameter"] / 2) ** 2) for c in cells for s in segments if s["tool"] == c["tool"]["id"]), 3),
                  limitations=["Printer macros/tool transforms are opaque", "Configured Z does not prove physical nozzle clearance", "No hardware print verified"])
    if gcode is not None:
        result["gcode_sha256"] = hashlib.sha256(gcode.encode()).hexdigest()
        result["audit"] = audit_gcode(gcode, p)
    return result


def preview_svg(p, segments):
    xmin, ymin = p["machine"]["safe_min"]
    xmax, ymax = p["machine"]["safe_max"]
    w, h = xmax - xmin, ymax - ymin
    colors = ["#2563eb", "#dc2626", "#059669", "#9333ea", "#d97706"]
    ids = [t["id"] for t in p["tools"]]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{xmin-4} {-ymax-4} {w+8} {h+20}">',
           f'<rect x="{xmin-4}" y="{-ymax-4}" width="{w+8}" height="{h+20}" fill="#f8fafc"/>',
           f'<rect x="{xmin}" y="{-ymax}" width="{w}" height="{h}" fill="white" stroke="#94a3b8" stroke-width="0.5"/>']
    for s in segments:
        color, a, b = colors[ids.index(s["tool"]) % len(colors)], s["a"], s["b"]
        out.append(f'<line x1="{a[0]}" y1="{-a[1]}" x2="{b[0]}" y2="{-b[1]}" stroke="{color}" stroke-width="{s["width"]}"><title>T{s["tool"]} {s["kind"]} row={s["row"]} Z={s["z"]:.4f}</title></line>')
    # Screen-only identification: never emitted as extrusion paths.
    cells, _ = layout(p)
    for c in sorted(cells, key=lambda c: c["x"]):
        out.append(f'<text x="{c["x"]}" y="{-c["y"]+4}" font-size="3">T{c["tool"]["id"]} (preview only)</text>')
    out.extend([f'<text x="{xmin}" y="{-ymin+6}" font-size="3">{html.escape(p["name"])} / {html.escape(p["test"]["direction"])} / row 0 = lowest Y</text>',
                f'<text x="{xmin}" y="{-ymin+11}" font-size="3">Safe nozzle XY region only; dock/macro motion is not shown.</text>', '</svg>'])
    return "\n".join(out) + "\n"


def write_new(path, content):
    """Publish atomically without replacing existing files, including symlinks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".oxplow-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path, value):
    write_new(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProfileError("Moonraker redirect rejected; use direct API URL")


class Moonraker:
    ALLOWED = {"/printer/info", "/printer/objects/list", "/printer/objects/query", "/printer/gcode/help"}

    def __init__(self, url, api_key=None, timeout=10):
        parts = parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ProfileError("Use direct http(s) Moonraker URL without credentials/query/fragment")
        self.base = url.rstrip("/")
        self.headers = {"Accept": "application/json"}
        if api_key:
            self.headers["X-Api-Key"] = api_key
        self.timeout = number(timeout, "timeout", 1, 60)
        self.opener = request.build_opener(NoRedirect())

    def get(self, endpoint, query=""):
        if endpoint not in self.ALLOWED:
            raise ProfileError("Endpoint is outside read-only allowlist")
        req = request.Request(self.base + endpoint + ("?" + query if query else ""), headers=self.headers, method="GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = response.read(8 * 1024 * 1024 + 1)
                if len(payload) > 8 * 1024 * 1024:
                    raise ProfileError("Moonraker response exceeds 8 MiB")
            data = json.loads(payload)
            if not isinstance(data, dict) or "result" not in data or "error" in data:
                raise ProfileError("Moonraker returned no valid result")
            return data["result"]
        except error.HTTPError as exc:
            raise ProfileError(f"Moonraker HTTP {exc.code}; check address/authentication") from None
        except (error.URLError, TimeoutError, OSError):
            raise ProfileError("Moonraker connection failed; check address/network/TLS/timeout") from None


def discover(client):
    info = client.get("/printer/info")
    if info.get("state") != "ready":
        raise ProfileError("Klipper must be ready to discover effective configuration")
    objects = client.get("/printer/objects/list").get("objects", [])
    required = {"configfile", "toolhead", "gcode_move", "heater_bed"}
    if not required.issubset(objects):
        raise ProfileError("Missing required printer objects")
    extruders = sorted(o for o in objects if re.fullmatch(r"extruder\d*", o))
    selected = sorted(required | set(extruders) | {o for o in objects if o.startswith("tool ")}
                      | ({"toolchanger", "print_stats", "gcode_macro _OXPLOW_CHECK"} & set(objects)))
    status = client.get("/printer/objects/query", "&".join(parse.quote(o, safe="") for o in selected)).get("status", {})
    settings = status.get("configfile", {}).get("settings", {})
    config = status.get("configfile", {}).get("config", {})
    if not settings or "toolhead" not in status:
        raise ProfileError("Moonraker did not return settings/toolhead")
    commands = client.get("/printer/gcode/help")
    return profile_from_snapshot(settings, config, status, commands, info.get("software_version", "unknown"))


def profile_from_snapshot(settings, config, status, commands, version):
    th = status["toolhead"]
    mins, maxs = th.get("axis_minimum"), th.get("axis_maximum")
    if not isinstance(mins, list) or not isinstance(maxs, list) or len(mins) < 3 or len(maxs) < 3:
        raise ProfileError("Missing XYZ bounds; cannot guess machine geometry")
    issues = ["safe_min/safe_max are axis bounds minus 10mm margin: review plate, docks, clips and ALL tool transforms",
              "Review start/end macro contracts and exact temperature parameter names",
              "Verify pickup/retraction state; set initial_retract only for a known start-macro remainder",
              "Temperature and flow caps are suggestions: adapt to filament/hotend",
              "Confirm offset storage/sign for installed toolchanger version"]
    live_mappings = [(int(v["tool_number"]), v["extruder"]) for k, v in status.items()
                     if k.startswith("tool ") and v.get("extruder") and int(v.get("tool_number", -1)) >= 0]
    mappings = live_mappings or [(int(v["tool_number"]), v["extruder"]) for k, v in settings.items()
                                if k.startswith("tool ") and "extruder" in v and "tool_number" in v]
    explicit = bool(mappings)
    if not mappings:
        extnames = sorted(s for s in settings if re.fullmatch(r"extruder\d*", s))
        mappings = [(0 if ext == "extruder" else int(ext[8:]), ext) for ext in extnames]
        issues.append("Tool IDs inferred from extruder names: UNVERIFIED without [tool ...] tool_number")
    if not mappings:
        raise ProfileError("No extruders found")
    tools = []
    printer_settings = settings.get("printer", {})
    for ident, ext in sorted(mappings):
        c = settings.get(ext)
        if not c or "nozzle_diameter" not in c or "filament_diameter" not in c:
            raise ProfileError(f"Missing extruder settings: {ext}")
        nozzle, filament = float(c["nozzle_diameter"]), float(c["filament_diameter"])
        selection = f"T{ident}" if f"T{ident}" in commands else ""
        if not selection and (len(mappings) > 1 or ident != 0):
            selection = "REVIEW_SELECT_TOOL"
            issues.append(f"T{ident}: no T macro found; replace REVIEW_SELECT_TOOL")
        tools.append(dict(id=ident, extruder=ext, select_gcode=selection, nozzle_diameter=nozzle,
                          filament_diameter=filament, temperature=min(210, float(c["max_temp"]) - 5),
                          min_extrude_temp=float(c.get("min_extrude_temp", 170)), max_temp=float(c["max_temp"]), material="REVIEW_MATERIAL",
                          max_extrude_cross_section=float(c.get("max_extrude_cross_section", 4 * nozzle ** 2)),
                          max_extrude_only_distance=float(c.get("max_extrude_only_distance", 50)),
                          max_extrude_only_velocity=float(c.get("max_extrude_only_velocity", float(printer_settings.get("max_velocity", 100)) * 4 * nozzle ** 2 / (math.pi * (filament / 2) ** 2))),
                          max_volumetric_flow=8, initial_retract=0,
                          temperature_command="toolchanger" if explicit and "SET_TOOL_TEMPERATURE" in commands else "named-heater"))
        reference = next((v for k, v in status.items() if k.startswith("tool ")
                          and v.get("tool_number") == ident and v.get("extruder") == ext), None)
        tools[-1]["saved_tool_z_offset"] = reference.get("gcode_z_offset") if reference else None
    macros = {k: v.get("gcode", "") for k, v in config.items() if k.lower().startswith("gcode_macro ")}
    p = dict(schema_version=1, name="Discovered Klipper - REVIEW REQUIRED", reviewed=False,
             machine=dict(safe_min=[float(mins[0]) + 10, float(mins[1]) + 10], safe_max=[float(maxs[0]) - 10, float(maxs[1]) - 10],
                          z_min=float(mins[2]), z_max=float(maxs[2]), travel_z=2, toolchange_z=min(20, float(maxs[2]) - 1),
                          bed_temp=60, bed_max_temp=float(settings["heater_bed"]["max_temp"]),
                          max_velocity=float(printer_settings.get("max_velocity", 100)),
                          max_z_velocity=float(printer_settings.get("max_z_velocity", printer_settings.get("max_velocity", 5)))),
             start_gcode=["REVIEW_START_MACRO"], end_gcode=["REVIEW_END_MACRO"], test={}, tools=tools, notes=issues,
             discovery=dict(klipper_version=version, config_sha256=digest(settings),
                            available_start_end=[k for k in commands if k in ("PRINT_START", "PRINT_END", "START_PRINT", "END_PRINT")],
                            capabilities=dict(runtime_guard="_OXPLOW_CHECK" in commands,
                                              runtime_version=status.get("gcode_macro _OXPLOW_CHECK", {}).get("oxplow_version"),
                                              native_variable="SET_GCODE_VARIABLE" in commands,
                                              preflight_variable="preflight_token" in status.get("gcode_macro _OXPLOW_CHECK", {}),
                                              define_objects="EXCLUDE_OBJECT_DEFINE" in commands,
                                              tool_temperature="SET_TOOL_TEMPERATURE" in commands),
                            tool_mapping_source="live tool registry" if live_mappings else ("tool sections" if explicit else "extruder inference")))
    relevant = {k: v for k, v in macros.items() if re.search(r"(?:PRINT_START|PRINT_END|START_PRINT|END_PRINT|T\d+)$", k, re.I)}
    # Follow literal macro calls for local review. Dynamic Jinja dispatch cannot be resolved here.
    macro_names = {k.split(maxsplit=1)[1].upper(): k for k in macros}
    pending = list(relevant)
    while pending:
        parent = pending.pop()
        for line in str(macros[parent]).splitlines():
            tokens = line.split(";", 1)[0].strip().split()
            dependency = macro_names.get(tokens[0].upper()) if tokens else None
            if dependency and dependency not in relevant:
                relevant[dependency] = macros[dependency]
                pending.append(dependency)
    evidence = dict(klipper_version=version, config_sha256=digest(settings), macros=relevant,
                    macro_scope="Start/end/T macros and literal dependencies; dynamic Jinja/plugin bodies require separate review",
                    tool_sections={k: {field: val for field, val in v.items() if field in ("tool_number", "extruder", "gcode_x_offset", "gcode_y_offset", "gcode_z_offset")}
                                   for k, v in settings.items() if k.startswith("tool ")},
                    live_state={k: status.get(k) for k in ("gcode_move", "toolhead", "toolchanger", "print_stats")})
    return p, evidence


def check_printer(profile, client):
    """Read-only compatibility check; never executes or uploads a print."""
    p = normalize_profile(profile)
    actual, evidence = discover(client)
    registered = {t["id"]: t for t in actual["tools"]}
    errors, warnings = [], []
    matches = True
    for t in p["tools"]:
        found = registered.get(t["id"])
        if found is None or found["extruder"] != t["extruder"]:
            errors.append(f"T{t['id']}: printer tool/extruder mapping differs")
            matches = False
            continue
        for key in ("nozzle_diameter", "filament_diameter"):
            if abs(t[key] - found[key]) > .0001:
                errors.append(f"T{t['id']}: {key} differs from printer")
                matches = False
        if t["saved_tool_z_offset"] is not None and (found.get("saved_tool_z_offset") is None
                or abs(t["saved_tool_z_offset"] - found["saved_tool_z_offset"]) > .0001):
            errors.append(f"T{t['id']}: saved/runtime tool Z reference differs; rediscover and review")
            matches = False
        elif t["saved_tool_z_offset"] is None:
            warnings.append(f"T{t['id']}: no saved tool Z reference; review offset application in the machine macros/plugin")
        if (t["temperature"] + p["test"]["temperature_tolerance"] >= found["max_temp"]
                or t["temperature"] - p["test"]["temperature_tolerance"] <= found["min_extrude_temp"]):
            errors.append(f"T{t['id']}: temperature outside printer extrusion limits")
            matches = False
        if (max(extrusion_area(t), annotation_area(t)) > found["max_extrude_cross_section"]
                or max(t["initial_retract"], p["test"]["retract_length"]) > found["max_extrude_only_distance"]
                or p["test"]["retract_speed"] > found["max_extrude_only_velocity"]):
            errors.append(f"T{t['id']}: extrusion/retraction exceeds printer limits")
            matches = False
    caps = actual["discovery"]["capabilities"]
    if not caps["runtime_guard"]:
        errors.append("Install oxplow_runtime.cfg before running generated G-code")
    elif caps["runtime_version"] != VERSION:
        errors.append("Update oxplow_runtime.cfg to the generator version")
    if not caps.get("native_variable", False):
        errors.append("Printer needs Klipper SET_GCODE_VARIABLE; review gcode_macro configuration")
    if caps["runtime_guard"] and not caps.get("preflight_variable", False):
        errors.append(f"Runtime guard lacks preflight_token; install the complete {VERSION} runtime cfg")
    if p["test"]["define_objects"] and not caps["define_objects"]:
        errors.append("Profile needs [exclude_object] / EXCLUDE_OBJECT_DEFINE")
    if any(t["temperature_command"] == "toolchanger" for t in p["tools"]) and not caps["tool_temperature"]:
        errors.append("Profile requires SET_TOOL_TEMPERATURE")
    if actual["machine"]["bed_max_temp"] <= p["machine"]["bed_temp"] + p["test"]["temperature_tolerance"]:
        errors.append("Bed temperature exceeds printer limit")
        matches = False
    th = evidence["live_state"]["toolhead"]
    if (max(p["test"]["print_speed"], p["test"]["annotation_speed"], p["test"]["travel_speed"]) > actual["machine"]["max_velocity"]
            or p["test"]["z_speed"] > actual["machine"]["max_z_velocity"]):
        errors.append("Profile speed exceeds printer limits")
        matches = False
    for axis in (0, 1):
        if p["machine"]["safe_min"][axis] < th["axis_minimum"][axis] or p["machine"]["safe_max"][axis] > th["axis_maximum"][axis]:
            errors.append("Profile safe XY rectangle exceeds printer axes")
            matches = False
    if th.get("homed_axes") != "xyz":
        warnings.append("Currently unhomed; reviewed start macro must perform XYZ homing")
    warnings.extend(["No commands were sent; startup/toolchange/mesh motion has not been executed",
                     "Check filament, physical clearances, mesh coverage and start-macro retract contract"])
    return dict(profile_matches_printer=matches, prerequisites_satisfied=not errors,
                reviewed=p["reviewed"], klipper_version=actual["discovery"]["klipper_version"],
                config_sha256=actual["discovery"]["config_sha256"], errors=errors, warnings=warnings)


def calculate(profile, tool_id, row=None, y=None, distance=None):
    p = normalize_profile(profile)
    cells, _ = layout(p)
    cell = next((c for c in cells if c["tool"]["id"] == tool_id), None)
    if cell is None:
        raise ProfileError("Unknown tool ID")
    if sum(v is not None for v in (row, y, distance)) != 1:
        raise ProfileError("Choose exactly one: row, Y or distance from lowest-Y row center")
    t, test = cell["tool"], p["test"]
    if row is not None:
        row = number(row, "row", 0, test["lines"] - 1)
        if not row.is_integer():
            raise ProfileError("row must be an integer, starting at zero")
        position = row
    elif y is not None:
        position = (number(y, "Y") - cell["y"]) / t["line_step"]
    else:
        position = number(distance, "distance") / t["line_step"]
    if position < -1e-8 or position > test["lines"] - 1 + 1e-8:
        raise ProfileError("Measurement outside ramp patch")
    z = row_z(t, test, max(0, min(position, test["lines"] - 1)))
    delta = z - t["nominal_height"]
    return dict(tool=tool_id, row_position=round(position, 5), best_z=round(z, 5), nominal_height=t["nominal_height"],
                runtime_z_adjust=round(delta, 5), interpretation="Positive raises nozzle; negative lowers nozzle in Klipper SET_GCODE_OFFSET",
                suggested_runtime_command=f"SET_GCODE_OFFSET Z_ADJUST={delta:+.5f} MOVE=0",
                storage="Do not copy sign into probe/per-tool config without checking its convention",
                boundary_result=position <= 0 or position >= test["lines"] - 1)


def package_release(destination):
    paths = [ROOT / "generate_oxplow_gcode.py", ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "AGENTS.md",
             ROOT / "profiles" / "klipper-toolchanger.example.json", ROOT / "profiles" / "ktc-prime-lines.example.json",
             ROOT / "oxplow_runtime.cfg"]
    paths += sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "tests").glob("test_*.py"))
    if any(not p.is_file() for p in paths):
        raise ProfileError("Missing release files")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            manifest = {}
            for path in paths:
                name, data = path.relative_to(ROOT).as_posix(), path.read_bytes()
                bundle.writestr(name, data)
                manifest[name] = hashlib.sha256(data).hexdigest()
            bundle.writestr("MANIFEST.sha256.json", json.dumps(manifest, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=f"Oxplow {VERSION}: Klipper calibration and read-only Moonraker discovery")
    commands = parser.add_subparsers(dest="command", required=True)
    d = commands.add_parser("discover", help="Read Moonraker; write draft profile + local evidence")
    d.add_argument("--url", required=True)
    d.add_argument("--api-key-env", default="MOONRAKER_API_KEY")
    d.add_argument("--timeout", type=float, default=10)
    d.add_argument("-o", "--output", type=Path, required=True)
    for name in ("validate", "generate", "calculate"):
        cmd = commands.add_parser(name)
        if name == "calculate":
            source = cmd.add_mutually_exclusive_group(required=True)
            source.add_argument("--profile", type=Path)
            source.add_argument("--report", type=Path, help="Use exact profile recorded in generated report")
        else:
            cmd.add_argument("--profile", type=Path, required=True)
        if name == "generate":
            cmd.add_argument("-o", "--output", type=Path, required=True)
            cmd.add_argument("--preview-only", action="store_true", help="SVG/report only; permits draft profiles")
        if name == "validate":
            cmd.add_argument("--url", help="Also check live Moonraker configuration with GET requests")
            cmd.add_argument("--api-key-env", default="MOONRAKER_API_KEY")
            cmd.add_argument("--timeout", type=float, default=10)
        if name == "calculate":
            cmd.add_argument("--tool", type=int, required=True)
            measure = cmd.add_mutually_exclusive_group(required=True)
            measure.add_argument("--row", type=int)
            measure.add_argument("--y", type=float)
            measure.add_argument("--distance", type=float)
    pkg = commands.add_parser("package", help="Build sharing candidate with SHA256 manifest")
    pkg.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "discover":
            profile, evidence = discover(Moonraker(args.url, os.environ.get(args.api_key_env), args.timeout))
            evidence_path = args.output.with_suffix(".evidence.local.json")
            if args.output.exists() or evidence_path.exists():
                raise ProfileError("Discovery output exists; choose a new filename")
            write_json(evidence_path, evidence)
            write_json(args.output, profile)
            print(f"Draft profile: {args.output}\nLocal evidence: {evidence_path}\nNo printer commands sent.")
        elif args.command == "package":
            package_release(args.output)
            print(f"Sharing candidate: {args.output}; hardware/license verification: docs/RELEASE.md")
        else:
            if args.command == "calculate" and args.report is not None:
                recorded = read_json(args.report)
                # Verify the original stored object before adding newer schema defaults.
                if recorded.get("profile_sha256") != digest(recorded["profile"]):
                    raise ProfileError("Report/profile hash mismatch; do not use edited calibration records")
                stored = copy.deepcopy(recorded["profile"])
                if recorded.get("version") in ("2.0.0", "2.1.0", "2.2.0", "2.2.1", "2.2.2"):
                    stored["test"].setdefault("annotations", True)
                if recorded.get("version") in ("2.0.0", "2.1.0", "2.2.0", "2.2.1"):
                    # Historical reports used the smaller label band. In particular,
                    # --y must not move its row origin when new layout defaults change.
                    stored["test"].setdefault("label_scale", 1.0)
                    for t in stored["tools"]:
                        t.setdefault("annotation_line_width", t.get("line_width", t["nozzle_diameter"] * 1.1))
                p = normalize_profile(stored)
            else:
                p = normalize_profile(read_json(args.profile), runnable=args.command == "generate" and not args.preview_only)
            cells, segments = layout(p)
            if args.command == "validate":
                result = dict(valid=True, reviewed=p["reviewed"], profile_sha256=digest(p), tools=[t["id"] for t in p["tools"]],
                              note="Static validation only")
                if args.url:
                    result["printer_check"] = check_printer(p, Moonraker(args.url, os.environ.get(args.api_key_env), args.timeout))
                print(json.dumps(result, indent=2))
                if args.url and not result["printer_check"]["prerequisites_satisfied"]:
                    return 2
            elif args.command == "calculate":
                print(json.dumps(calculate(p, args.tool, args.row, args.y, args.distance), indent=2))
            else:
                suffix = ".svg" if args.preview_only else ".gcode"
                if args.output.suffix.lower() != suffix:
                    raise ProfileError(f"Output must end in {suffix}")
                svg_path = args.output.with_suffix(".svg")
                report_path = args.output.with_suffix(".report.json")
                destinations = [svg_path, report_path] + ([] if args.preview_only else [args.output])
                if any(path.exists() for path in destinations):
                    raise ProfileError("Output exists; choose a new basename")
                gcode = None if args.preview_only else generate_oxplow_gcode(p)
                report = report_for(p, cells, segments, gcode)
                write_new(svg_path, preview_svg(p, segments))
                write_json(report_path, report)
                if gcode is not None:
                    write_new(args.output, gcode)
                print(f"Preview: {svg_path}\nReport: {report_path}")
                if gcode is not None:
                    print(f"G-code: {args.output}\nAudit: {report['audit']}")
        return 0
    except (ProfileError, ValueError, TypeError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
