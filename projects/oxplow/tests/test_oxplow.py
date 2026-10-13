"""Regression tests for geometry, safety constraints, CLI and read-only discovery."""
import contextlib
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import generate_oxplow_gcode as ox


def profile():
    p = ox.read_json(ROOT / "profiles" / "klipper-toolchanger.example.json")
    p["name"] = "SYNTHETIC TEST FIXTURE - NOT A HARDWARE PROFILE"
    p["reviewed"] = True
    p["test"]["annotations"] = True  # Explicit legacy coverage; new default is patch-only.
    return p


class GeometryTests(unittest.TestCase):
    def test_default_has_only_ramp_and_balanced_entry_recovery(self):
        p = profile()
        p["test"].pop("annotations")
        p["tools"][0]["initial_retract"] = .6
        n = ox.normalize_profile(p)
        self.assertFalse(n["test"]["annotations"])
        cells, segments = ox.layout(n)
        self.assertEqual({s["kind"] for s in segments}, {"row", "connector"})
        code = ox.generate_oxplow_gcode(p)
        for marker in ("; label Z=", "; tick Z=", "; purge Z=", "; lead_in Z=", "short label travel"):
            self.assertNotIn(marker, code)
        self.assertEqual(code.count("recover known start-macro retract"), 1)
        e_only = [float(line.split()[1][1:]) for line in code.splitlines() if line.startswith("G1 E")]
        self.assertAlmostEqual(sum(e_only), .6 - len(p["tools"]) * p["test"].get("retract_length", .6))
        self.assertEqual(ox.audit_gcode(code, p)["rows_checked"], 102)
        report = ox.report_for(n, cells, segments, code)
        self.assertEqual(report["annotations"], [])

    def test_patch_positions_increase_numeric_id_preserving_print_order(self):
        p = profile()
        p["test"]["annotations"] = False
        p["tools"].reverse()
        p["tools"][0].update(id=10, select_gcode="T10")
        p["tools"][1].update(id=2, select_gcode="T2")
        n = ox.normalize_profile(p)
        cells, segments = ox.layout(n)
        self.assertEqual([c["tool"]["id"] for c in cells], [10, 2])
        self.assertGreater(cells[0]["x"], cells[1]["x"])
        code = ox.generate_oxplow_gcode(p)
        self.assertIn("; Left-to-right (+X): T2 -> T10", code)
        self.assertLess(code.index("; BEGIN TOOL T10"), code.index("; BEGIN TOOL T2"))
        report = ox.report_for(n, cells, segments, code)
        self.assertEqual([r["tool"] for r in report["patches_left_to_right"]], [2, 10])
        self.assertIn("T2 (preview only)", ox.preview_svg(n, segments))

    def test_patch_only_y_measurement_and_bounds(self):
        p = profile()
        p["test"].update(annotations=False, direction="low-to-high")
        n = ox.normalize_profile(p)
        cells, _ = ox.layout(n)
        t = cells[0]["tool"]
        self.assertAlmostEqual(ox.calculate(n, t["id"], y=cells[0]["y"])["best_z"],
                               t["nominal_height"] - t["ramp_range"])
        self.assertAlmostEqual(ox.calculate(n, t["id"], distance=cells[0]["height"])["best_z"],
                               t["nominal_height"] + t["ramp_range"])
        p["test"]["center"] = p["machine"]["safe_min"]
        with self.assertRaisesRegex(ox.ProfileError, "footprint"):
            ox.generate_oxplow_gcode(p)

    def test_annotations_flag_rejects_truthy_strings(self):
        p = profile()
        p["test"]["annotations"] = "false"
        with self.assertRaisesRegex(ox.ProfileError, "annotations must be boolean"):
            ox.normalize_profile(p)

    def test_patch_only_end_macro_owns_last_retract(self):
        p = profile()
        p["tools"] = p["tools"][:1]
        p["tools"][0]["initial_retract"] = .6
        p["test"].update(annotations=False, end_retract_owner="end_macro")
        code = ox.generate_oxplow_gcode(p)
        self.assertNotIn("G1 E-", code)
        self.assertEqual(code.count("recover known start-macro retract"), 1)
        ox.audit_gcode(code, p)

    def test_final_macro_lift_is_deferred_but_intermediate_tool_lift_stays(self):
        p = profile()
        p["test"].update(annotations=False, end_retract_owner="end_macro", end_lift_owner="end_macro")
        code = ox.generate_oxplow_gcode(p)
        first = code.split("; BEGIN TOOL T0")[1].split("; END TOOL T0")[0]
        last = code.split("; BEGIN TOOL T1")[1].split("; END TOOL T1")[0]
        self.assertIn("G1 E-0.60000", first)
        self.assertTrue(first.rstrip().endswith("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0"))
        self.assertIn("G0 Z20.0000", first)
        last_row = last.split("; ROW T1 INDEX=50")[1]
        self.assertNotIn("G0", last_row)
        self.assertNotIn("G1 E-", last_row)
        self.assertIn("Final retract/lift handed", last_row)
        self.assertEqual(code.count("Final retract/lift handed"), 1)
        ox.audit_gcode(code, p)

    def test_final_lift_owner_requires_shared_end_macro_contract(self):
        p = profile()
        p["test"]["end_lift_owner"] = "end_macro"
        with self.assertRaisesRegex(ox.ProfileError, "requires end_retract_owner"):
            ox.normalize_profile(p)
        p["test"]["end_lift_owner"] = "false"
        with self.assertRaisesRegex(ox.ProfileError, "end_lift_owner is"):
            ox.normalize_profile(p)

    def test_audit_rejects_changed_row_or_connector_extrusion_below_flow_cap(self):
        p = profile()
        p["test"]["annotations"] = False
        code = ox.generate_oxplow_gcode(p)
        for marker in ("; ROW T0 INDEX=0", "; connector Z="):
            lines = code.splitlines()
            i = next(i for i, line in enumerate(lines) if line.startswith(marker)) + 1
            parts = lines[i].split()
            for j, part in enumerate(parts):
                if part.startswith("E"):
                    parts[j] = f"E{float(part[1:]) * 1.2:.5f}"
            lines[i] = " ".join(parts)
            with self.assertRaisesRegex(ox.ProfileError, "extrusion differs from profile"):
                ox.audit_gcode("\n".join(lines), p)

    def test_audit_rejects_travel_z_and_extrude_only_velocity(self):
        p = profile()
        p["test"]["annotations"] = False
        p["tools"][0]["initial_retract"] = .6
        code = ox.generate_oxplow_gcode(p)
        n = ox.normalize_profile(p)
        for prefix, feed in (("G0 X", 60 * (n["machine"]["max_velocity"] + 10)),
                             ("G0 Z", 60 * (n["machine"]["max_z_velocity"] + 1)),
                             ("G1 E", 60 * (n["tools"][0]["max_extrude_only_velocity"] + 10))):
            lines = code.splitlines()
            i = next(i for i, line in enumerate(lines) if line.startswith(prefix))
            parts = lines[i].split(";", 1)[0].split()
            lines[i] = " ".join(part for part in parts if not part.startswith("F")) + f" F{feed}"
            with self.assertRaisesRegex(ox.ProfileError, "velocity"):
                ox.audit_gcode("\n".join(lines), p)

    def test_audit_handles_quantized_small_connectors_and_modal_feed(self):
        p = profile()
        p["test"]["annotations"] = False
        p["tools"] = p["tools"][:1]
        t = p["tools"][0]
        for k in ("nominal_height", "ramp_range", "line_width", "line_step", "annotation_height", "annotation_line_width"):
            t.pop(k, None)
        t.update(nozzle_diameter=.15, filament_diameter=3.5)
        code = ox.generate_oxplow_gcode(p)
        ox.audit_gcode(code, p)
        lines = code.splitlines()
        i = next(i for i, line in enumerate(lines) if line.startswith("; connector Z=")) + 1
        lines[i] = " ".join(part for part in lines[i].split() if not part.startswith("F"))
        ox.audit_gcode("\n".join(lines), p)

    def test_audit_checks_z_component_of_mixed_connector(self):
        p = profile()
        p["test"]["annotations"] = False
        lines = ox.generate_oxplow_gcode(p).splitlines()
        i = next(i for i, line in enumerate(lines) if line.startswith("; connector Z=")) + 1
        lines[i] = " ".join("Z10" if part.startswith("Z") else part for part in lines[i].split())
        with self.assertRaisesRegex(ox.ProfileError, "Z velocity"):
            ox.audit_gcode("\n".join(lines), p)

    def test_annotation_width_changes_only_annotation_extrusion(self):
        p = profile()
        p["tools"][0]["annotation_line_width"] = .44
        narrow = ox.generate_oxplow_gcode(p).splitlines()
        p["tools"][0]["annotation_line_width"] = .6
        wide = ox.generate_oxplow_gcode(p).splitlines()
        rows = lambda lines: [lines[i + 1] for i, line in enumerate(lines) if line.startswith("; ROW")]
        self.assertEqual(rows(narrow), rows(wide))
        e = lambda lines: float(next(lines[i + 1] for i, line in enumerate(lines) if line.startswith("; label")).split(" E")[1].split()[0])
        self.assertGreater(e(wide), e(narrow))
        ox.audit_gcode("\n".join(wide), p)

    def test_lead_in_joins_first_stem_without_retract_or_lift(self):
        p = ox.normalize_profile(profile())
        _, segments = ox.layout(p)
        lead = next(i for i, s in enumerate(segments) if s["kind"] == "lead_in")
        self.assertEqual(segments[lead]["b"], segments[lead + 1]["a"])
        self.assertEqual(segments[lead]["z"], segments[lead + 1]["z"])
        code = ox.generate_oxplow_gcode(p)
        between = code.split("; lead_in Z=", 1)[1].split("; label Z=", 1)[0]
        self.assertNotIn("G0", between)
        self.assertNotIn("G1 E", between)
        ox.audit_gcode(code, p)

    def test_large_labels_and_wide_annotations_are_bounds_checked(self):
        p = profile()
        p["test"]["label_scale"] = 3
        p["tools"][1].update(id=999, select_gcode="T999", annotation_line_width=.8)
        ox.audit_gcode(ox.generate_oxplow_gcode(p), p)
        p["test"]["center"] = p["machine"]["safe_min"].copy()
        with self.assertRaisesRegex(ox.ProfileError, "footprint"):
            ox.generate_oxplow_gcode(p)

    def test_annotation_width_obeys_flow_and_nozzle_limits(self):
        p = profile()
        p["tools"][0]["annotation_line_width"] = .81
        with self.assertRaisesRegex(ox.ProfileError, "annotation_line_width"):
            ox.normalize_profile(p)
        p["tools"][0].update(annotation_line_width=.8, max_volumetric_flow=1)
        p["test"].update(print_speed=1, annotation_speed=10)
        with self.assertRaisesRegex(ox.ProfileError, "flow"):
            ox.normalize_profile(p)

    def test_digit_trails_preserve_every_font_edge_once(self):
        for char, segments in ox.FONT.items():
            expected = sorted(tuple(sorted(ox.SEGMENTS[s])) for s in segments)
            actual = sorted(tuple(sorted(stroke)) for stroke in ox.generate_char_strokes(char, 0, 0, 1, 1))
            self.assertEqual(actual, expected, char)
        zero = ox.generate_char_strokes("0", 0, 0, 3, 5)
        self.assertTrue(all(a[1] == b[0] for a, b in zip(zero, zero[1:])))
        self.assertEqual(zero[-1][1], zero[0][0])

    def test_letters_have_no_internal_retract_or_lift(self):
        code = ox.generate_oxplow_gcode(profile())
        labels = code.split("; label Z=", 1)[1].split("; tick Z=", 1)[0]
        # Stop before the transition into ticks, which deliberately retracts/lifts.
        labels = labels.rsplit("G1 E-", 1)[0]
        self.assertNotIn("G1 E-", labels)
        self.assertNotIn("G0 Z", labels)
        self.assertIn("short label travel", labels)
        ox.audit_gcode(code, profile())

    def test_label_travel_is_exactly_bounded_and_slow(self):
        code = ox.generate_oxplow_gcode(profile())
        lines = code.splitlines()
        i = next(i for i, line in enumerate(lines) if "short label travel" in line)
        for replacement in ("G0 X100 Y100 F600", lines[i].replace("F600", "F6000")):
            bad = lines.copy()
            bad[i] = replacement
            with self.assertRaisesRegex(ox.ProfileError, "unlifted XY travel"):
                ox.audit_gcode("\n".join(bad), profile())

    def test_annotation_speed_does_not_change_ramp(self):
        p = profile()
        original = ox.generate_oxplow_gcode(p).splitlines()
        p["test"]["annotation_speed"] = 7
        modified = ox.generate_oxplow_gcode(p).splitlines()
        rows = lambda lines: [lines[i + 1] for i, line in enumerate(lines) if line.startswith("; ROW")]
        self.assertEqual(rows(original), rows(modified))
        self.assertTrue(all(modified[i + 1].endswith("F420") for i, line in enumerate(modified) if line.startswith("; label")))
        ox.audit_gcode("\n".join(modified), p)

    def test_annotation_speed_obeys_velocity_and_flow(self):
        p = profile()
        p["test"].update(print_speed=1, travel_speed=1, annotation_speed=100)
        p["machine"]["max_velocity"] = 50
        with self.assertRaisesRegex(ox.ProfileError, "velocity"):
            ox.normalize_profile(p)
        p["machine"]["max_velocity"] = 200
        p["tools"][0]["max_volumetric_flow"] = 1
        with self.assertRaisesRegex(ox.ProfileError, "flow"):
            ox.normalize_profile(p)

    def test_annotations_keep_baseline_while_test_z_is_adjusted(self):
        p = profile()
        p["tools"][0].update(annotation_height=.2, annotation_z_adjust=0, test_z_adjust=.03, saved_tool_z_offset=.1665)
        p = ox.normalize_profile(p)
        _, strokes = ox.layout(p)
        self.assertTrue(all(s["z"] == .2 for s in strokes if s["tool"] == 0 and s["kind"] in ("label", "tick", "purge")))
        center = next(s for s in strokes if s["tool"] == 0 and s["kind"] == "row" and s["row"] == 25)
        self.assertAlmostEqual(center["z"], .27)
        self.assertAlmostEqual(ox.calculate(p, 0, row=25)["runtime_z_adjust"], .03)
        ox.audit_gcode(ox.generate_oxplow_gcode(p), p)

    def test_saved_offsets_are_references_never_added_to_z(self):
        for saved in (-.3515, .1665, 0):
            p = profile()
            p["tools"][0]["saved_tool_z_offset"] = saved
            code = ox.generate_oxplow_gcode(p)
            self.assertIn(f"SAVED_Z={saved:.6f}", code)
            self.assertIn("; label Z=0.2000", code)
            self.assertIn("; ROW T0 INDEX=25", code)
            ox.audit_gcode(code, p)

    def test_annotation_extrusion_matches_its_own_height(self):
        p = ox.normalize_profile(profile())
        _, strokes = ox.layout(p)
        self.assertTrue(all(s["extrusion_height"] == .2 for s in strokes if s["kind"] == "label"))
        self.assertTrue(all(s["extrusion_height"] == .24 for s in strokes if s["kind"] in ("row", "connector")))
        self.assertLess(ox.extrusion_area(p["tools"][0], .2), ox.extrusion_area(p["tools"][0]))

    def test_annotation_adjustment_does_not_change_ramp(self):
        p = profile()
        p["tools"][0].update(annotation_height=.2, annotation_z_adjust=-.02)
        code = ox.generate_oxplow_gcode(p)
        self.assertIn("; label Z=0.1800", code)
        self.assertEqual(ox.calculate(p, 0, row=25)["runtime_z_adjust"], 0)
        ox.audit_gcode(code, p)

    def test_native_install_probe_is_first_executable_command(self):
        code = ox.generate_oxplow_gcode(profile())
        first = next(line for line in code.splitlines() if line and not line.startswith(";"))
        self.assertEqual(first, "SET_GCODE_VARIABLE MACRO=_OXPLOW_CHECK VARIABLE=preflight_token VALUE=1")
        with self.assertRaisesRegex(ox.ProfileError, "preflight"):
            ox.audit_gcode(code.replace(first + "\n", ""), profile())

    def test_audit_rejects_annotation_z_and_extrusion_tampering(self):
        code = ox.generate_oxplow_gcode(profile())
        lines = code.splitlines()
        label_index = next(i for i, line in enumerate(lines) if line.startswith("; label Z=")) + 1
        bad = lines.copy()
        bad[label_index] = bad[label_index].replace("Z0.2000", "Z0.2800")
        with self.assertRaisesRegex(ox.ProfileError, "Annotation Z"):
            ox.audit_gcode("\n".join(bad), profile())
        bad = lines.copy()
        parts = bad[label_index].split()
        parts = ["E0.05000" if s.startswith("E") else s for s in parts]
        bad[label_index] = " ".join(parts)
        with self.assertRaisesRegex(ox.ProfileError, "Annotation extrusion"):
            ox.audit_gcode("\n".join(bad), profile())

    def test_two_tools_full_audit(self):
        p = profile()
        result = ox.audit_gcode(ox.generate_oxplow_gcode(p), p)
        self.assertEqual(result["tools_checked"], 2)
        self.assertEqual(result["rows_checked"], 102)

    def test_single_nonzero_tool_is_selected(self):
        p = profile()
        p["tools"] = p["tools"][1:]
        code = ox.generate_oxplow_gcode(p)
        self.assertIn("\nT1\nG90\nM83\n", code)
        self.assertEqual(ox.audit_gcode(code, p)["tools_checked"], 1)

    def test_single_extruder_may_omit_tool_macro(self):
        p = profile()
        p["tools"] = p["tools"][:1]
        p["tools"][0]["select_gcode"] = ""
        self.assertNotIn("\nT0\n", ox.generate_oxplow_gcode(p))

    def test_multi_digit_font_and_relative_four(self):
        p = profile()
        p["tools"][1].update(id=14, select_gcode="T14")
        normalized = ox.normalize_profile(p)
        _, segments = ox.layout(normalized)
        label = [s for s in segments if s["tool"] == 14 and s["kind"] == "label"]
        self.assertEqual(len(label), 2 + len(ox.FONT["1"]) + len(ox.FONT["4"]))
        strokes = ox.generate_char_strokes("4", 150, 80, 3, 5)
        self.assertTrue(all(150 <= x <= 153 and 80 <= y <= 85 for stroke in strokes for x, y in stroke))

    def test_adaptive_nozzle_sizes(self):
        for d in (.2, .4, .6, .8, 1.2):
            with self.subTest(nozzle=d):
                p = profile()
                for t in p["tools"]:
                    t["nozzle_diameter"] = d
                    del t["nominal_height"], t["ramp_range"]
                    t["max_volumetric_flow"] = 100
                self.assertEqual(ox.audit_gcode(ox.generate_oxplow_gcode(p), p)["rows_checked"], 102)

    def test_mixed_nozzles_and_filament(self):
        p = profile()
        p["tools"][1].update(nozzle_diameter=.6, nominal_height=.3, ramp_range=.05, filament_diameter=2.85)
        self.assertEqual(ox.audit_gcode(ox.generate_oxplow_gcode(p), p)["tools_checked"], 2)

    def test_constant_row_extrusion(self):
        code = ox.generate_oxplow_gcode(profile()).splitlines()
        es = [code[i + 1].split(" E")[1].split()[0] for i, line in enumerate(code) if line.startswith("; ROW")]
        self.assertEqual(len(set(es)), 1)

    def test_retract_balanced_between_strokes_no_initial_unretract(self):
        code = ox.generate_oxplow_gcode(profile())
        for body in code.split("; BEGIN TOOL ")[1:]:
            body = body.split("; END TOOL")[0]
            amounts = [float(line.split()[1][1:]) for line in body.splitlines() if line.startswith("G1 E")]
            self.assertLess(amounts[0], 0)
            self.assertAlmostEqual(sum(amounts), -.6, places=5)

    def test_first_xy_after_selection_at_toolchange_height(self):
        lines = ox.generate_oxplow_gcode(profile()).splitlines()
        for i, line in enumerate(lines):
            if line in ("T0", "T1"):
                j = next(j for j in range(i + 1, len(lines)) if lines[j].startswith("G0 X"))
                self.assertIn("Z20.0000", lines[j - 1])

    def test_direction_center_and_runtime_sign(self):
        for direction in ("high-to-low", "low-to-high"):
            p = profile()
            p["test"]["direction"] = direction
            center = ox.calculate(p, 0, row=25)
            self.assertEqual(center["runtime_z_adjust"], 0)
            delta = ox.calculate(p, 0, row=35)["runtime_z_adjust"]
            self.assertAlmostEqual(delta, -.024 if direction == "high-to-low" else .024)

    def test_measurement_modes_agree(self):
        p = ox.normalize_profile(profile())
        cells, _ = ox.layout(p)
        a = ox.calculate(p, 0, row=35)
        distance = 35 * p["tools"][0]["line_step"]
        b = ox.calculate(p, 0, y=cells[0]["y"] + distance)
        c = ox.calculate(p, 0, distance=distance)
        self.assertEqual(a["runtime_z_adjust"], b["runtime_z_adjust"])
        self.assertEqual(a["runtime_z_adjust"], c["runtime_z_adjust"])

    def test_zero_range_confirmation(self):
        p = profile()
        for t in p["tools"]:
            t["ramp_range"] = 0
        self.assertEqual(ox.calculate(p, 0, row=50)["runtime_z_adjust"], 0)
        ox.audit_gcode(ox.generate_oxplow_gcode(p), p)

    def test_default_spacing_matches_nominal_bead_area(self):
        p = ox.normalize_profile(profile())
        for t in p["tools"]:
            self.assertAlmostEqual(t["line_step"] * t["nominal_height"], ox.extrusion_area(t))

    def test_initial_retract_recovered_once_per_tool(self):
        p = profile()
        p["tools"][0]["initial_retract"] = .6
        p["tools"][1]["initial_retract"] = 1.8
        code = ox.generate_oxplow_gcode(p)
        self.assertEqual(code.count("recover known start-macro retract"), 2)
        for body, expected in zip(code.split("; BEGIN TOOL ")[1:], (0, 1.2)):
            amounts = [float(line.split()[1][1:]) for line in body.split("; END TOOL")[0].splitlines() if line.startswith("G1 E")]
            self.assertAlmostEqual(sum(amounts), expected)
        ox.audit_gcode(code, p)

    def test_temperature_set_before_pickup(self):
        p = profile()
        p["tools"][1]["temperature_command"] = "toolchanger"
        code = ox.generate_oxplow_gcode(p)
        start = code.index("; BEGIN TOOL T1")
        self.assertLess(code.index("SET_TOOL_TEMPERATURE T=1 TARGET=210", start), code.index("\nT1\n", start))

    def test_end_macro_owns_last_retract_and_heater(self):
        p = profile()
        p["test"]["end_retract_owner"] = "end_macro"
        code = ox.generate_oxplow_gcode(p)
        body = code.split("; BEGIN TOOL T1")[1].split("; END TOOL T1")[0]
        amounts = [float(line.split()[1][1:]) for line in body.splitlines() if line.startswith("G1 E")]
        self.assertAlmostEqual(sum(amounts), 0)
        self.assertNotIn("HEATER=extruder1 TARGET=0", body)
        self.assertIn("HEATER=extruder TARGET=0", code)
        self.assertTrue(code.index("PRINT_END") < code.index("TURN_OFF_HEATERS"))

    def test_mesh_objects_defined_before_start_and_include_all_strokes(self):
        p = profile()
        p["test"]["define_objects"] = True
        p = ox.normalize_profile(p)
        _, segments = ox.layout(p)
        code = ox.generate_oxplow_gcode(p)
        self.assertLess(code.index("EXCLUDE_OBJECT_DEFINE RESET=1"), code.index("PRINT_START"))
        definitions = [line for line in code.splitlines() if "POLYGON=" in line]
        self.assertEqual(len(definitions), 2)
        for tool, line in zip(p["tools"], definitions):
            poly = json.loads(line.split("POLYGON=")[1])
            for s in segments:
                if s["tool"] == tool["id"]:
                    for x, y in (s["a"], s["b"]):
                        self.assertLessEqual(poly[0][0], x - s["width"] / 2)
                        self.assertLessEqual(x + s["width"] / 2, poly[2][0])
                        self.assertLessEqual(poly[0][1], y - s["width"] / 2)
                        self.assertLessEqual(y + s["width"] / 2, poly[2][1])
        ox.audit_gcode(code, p)

    def test_boundary_result(self):
        self.assertTrue(ox.calculate(profile(), 0, row=0)["boundary_result"])
        self.assertFalse(ox.calculate(profile(), 0, row=25)["boundary_result"])

    def test_no_shell_mesh_or_automatic_offset_or_motor_off(self):
        code = ox.generate_oxplow_gcode(profile())
        executable = "\n".join(line for line in code.splitlines() if not line.startswith(";"))
        for token in ("||", "2>/dev/null", "M104 T", "M109 T", "SAVE_CONFIG", "SET_GCODE_OFFSET", "M84", "BED_MESH_PROFILE"):
            self.assertNotIn(token, executable)

    def test_report_hash_and_svg_parse(self):
        import xml.etree.ElementTree as ET
        p = ox.normalize_profile(profile())
        cells, segments = ox.layout(p)
        code = ox.generate_oxplow_gcode(p)
        report = ox.report_for(p, cells, segments, code)
        self.assertIn(report["profile_sha256"], code)
        self.assertEqual(len(report["rows"]), 102)
        ET.fromstring(ox.preview_svg(p, segments))


class ValidationTests(unittest.TestCase):
    def rejects(self, mutate):
        p = profile()
        mutate(p)
        with self.assertRaises(ox.ProfileError):
            ox.generate_oxplow_gcode(p)

    def test_draft_cannot_generate(self):
        self.rejects(lambda p: p.update(reviewed=False))

    def test_annotation_and_adjusted_ramp_cannot_cross_clearance_limits(self):
        for field, value in (("annotation_z_adjust", -.2), ("annotation_z_adjust", .5),
                             ("test_z_adjust", -.3), ("test_z_adjust", .5),
                             ("annotation_height", True), ("saved_tool_z_offset", "0.1")):
            self.rejects(lambda p, k=field, v=value: p["tools"][0].update({k: v}))

    def test_duplicate_empty_tools(self):
        for mutation in (lambda p: p.update(tools=[]), lambda p: p["tools"][1].update(id=0),
                         lambda p: p["tools"][1].update(extruder="extruder")):
            self.rejects(mutation)

    def test_nonfinite_and_wrong_types(self):
        for value in (float("nan"), float("inf"), True, "0.4"):
            self.rejects(lambda p, v=value: p["tools"][0].update(nozzle_diameter=v))

    def test_line_counts_and_precision(self):
        for count in (0, 1, 2, 50, 1002, True):
            self.rejects(lambda p, n=count: p["test"].update(lines=n))
        self.rejects(lambda p: p["tools"][0].update(ramp_range=.0001))

    def test_unknown_fields_and_negative_ramp(self):
        self.rejects(lambda p: p["test"].update(prnit_speed=30))
        self.rejects(lambda p: p["tools"][0].update(ramp_range=-.1))
        self.rejects(lambda p: p["tools"][0].update(initial_retract=-.6))
        self.rejects(lambda p: p["tools"][0].update(initial_retract=40, max_extrude_only_distance=10))
        self.rejects(lambda p: p["tools"][0].update(temperature_command="M104 T"))

    def test_z_boundaries(self):
        for mutation in (lambda p: p["machine"].update(toolchange_z=400),
                         lambda p: p["tools"][0].update(ramp_range=.24),
                         lambda p: p["machine"].update(z_min=.2),
                         lambda p: p["machine"].update(travel_z=.1)):
            self.rejects(mutation)

    def test_xy_full_footprint_and_center(self):
        self.rejects(lambda p: p["machine"].update(safe_max=[60, 60]))
        self.rejects(lambda p: p["test"].update(center=[20, 20]))

    def test_temperature_flow_and_speeds(self):
        for mutation in (lambda p: p["tools"][0].update(temperature=169),
                         lambda p: p["tools"][0].update(temperature=299),
                         lambda p: p["machine"].update(bed_temp=120),
                         lambda p: p["tools"][0].update(max_volumetric_flow=.1),
                         lambda p: p["tools"][0].update(max_extrude_cross_section=.001),
                         lambda p: p["machine"].update(max_velocity=50),
                         lambda p: p["tools"][0].update(max_extrude_only_velocity=10)):
            self.rejects(mutation)

    def test_bad_macros_and_missing_selection(self):
        for line in ("BED_MESH_PROFILE LOAD=default 2>/dev/null || G29", "SAVE_CONFIG", "M420 S1", "REVIEW_START_MACRO", "PRINT_START\nG28"):
            self.rejects(lambda p, line=line: p.update(start_gcode=[line]))
        self.rejects(lambda p: p["tools"][1].update(select_gcode=""))

    def test_outside_measurements(self):
        for kwargs in (dict(row=-1), dict(row=51), dict(distance=21), dict(row=25, y=100), dict(row=2.5)):
            with self.assertRaises(ox.ProfileError):
                ox.calculate(profile(), 0, **kwargs)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"name":"a","name":"b"}')
            with self.assertRaises(ox.ProfileError):
                ox.read_json(path)

    def test_audit_catches_tampering(self):
        p = profile()
        code = ox.generate_oxplow_gcode(p)
        for changed in (code.replace("G0 X", "G0 X9999 ;", 1), code.replace("G0 Z2.0000", "G0 Z0.1000", 1),
                        code.replace("INDEX=0", "INDEX=7", 1), code.replace("G90", "G91", 1)):
            with self.assertRaises(ox.ProfileError):
                ox.audit_gcode(changed, p)


def snapshot():
    settings = {
        "printer": dict(max_velocity=300, max_z_velocity=15), "heater_bed": dict(max_temp=120),
        "extruder": dict(nozzle_diameter=.4, filament_diameter=1.75, min_extrude_temp=170, max_temp=300),
        "extruder1": dict(nozzle_diameter=.6, filament_diameter=1.75, min_extrude_temp=170, max_temp=300),
        "tool reference": dict(tool_number=3, extruder="extruder", gcode_z_offset=.1),
        "tool other": dict(tool_number=9, extruder="extruder1"),
    }
    config = {"gcode_macro PRINT_START": {"gcode": "G28\nQUAD_GANTRY_LEVEL"}, "gcode_macro T3": {"gcode": "SELECT_TOOL T=3"},
              "unrelated_secret": {"secret": "DO_NOT_SERIALIZE"}}
    status = dict(toolhead=dict(axis_minimum=[0, 0, 0, 0], axis_maximum=[350, 350, 330, 0]),
                  configfile=dict(settings=settings, config=config), gcode_move={}, heater_bed={})
    commands = dict(T3="select 3", T9="select 9", PRINT_START="start", PRINT_END="end")
    return settings, config, status, commands


class DiscoveryAndCLITests(unittest.TestCase):
    def test_explicit_mapping_and_local_evidence(self):
        s, c, status, commands = snapshot()
        p, evidence = ox.profile_from_snapshot(s, c, status, commands, "test-version")
        self.assertEqual([t["id"] for t in p["tools"]], [3, 9])
        self.assertFalse(p["reviewed"])
        self.assertEqual(p["tools"][1]["select_gcode"], "T9")
        self.assertIn("gcode_macro PRINT_START", evidence["macros"])
        self.assertNotIn("DO_NOT_SERIALIZE", json.dumps((p, evidence)))

    def test_live_assign_tool_mapping_takes_priority(self):
        s, c, status, commands = snapshot()
        status["tool reference"] = dict(tool_number=7, extruder="extruder")
        status["tool other"] = dict(tool_number=12, extruder="extruder1")
        commands.update(T7="", T12="", SET_TOOL_TEMPERATURE="")
        p, _ = ox.profile_from_snapshot(s, c, status, commands, "test")
        self.assertEqual([t["id"] for t in p["tools"]], [7, 12])
        self.assertEqual(p["discovery"]["tool_mapping_source"], "live tool registry")
        self.assertEqual(p["tools"][0]["temperature_command"], "toolchanger")

    def test_live_check_reports_missing_guard_and_mapping_change(self):
        p = profile()
        actual = ox.normalize_profile(p)
        actual["discovery"] = dict(capabilities=dict(runtime_guard=False, runtime_version=None, define_objects=True, tool_temperature=True),
                                   klipper_version="test", config_sha256="test")
        evidence = dict(live_state=dict(toolhead=dict(axis_minimum=[0, 0, 0], axis_maximum=[350, 350, 330], homed_axes="")))
        with mock.patch.object(ox, "discover", return_value=(actual, evidence)):
            result = ox.check_printer(p, mock.Mock())
            self.assertTrue(result["profile_matches_printer"])
            self.assertFalse(result["prerequisites_satisfied"])
            actual["tools"][1]["extruder"] = "extruder9"
            self.assertFalse(ox.check_printer(p, mock.Mock())["profile_matches_printer"])

    def test_live_check_accepts_current_guard_version(self):
        p = profile()
        actual = ox.normalize_profile(p)
        actual["discovery"] = dict(capabilities=dict(runtime_guard=True, runtime_version=ox.VERSION, define_objects=True, tool_temperature=True,
                                                    native_variable=True, preflight_variable=True),
                                   klipper_version="test", config_sha256="test")
        evidence = dict(live_state=dict(toolhead=dict(axis_minimum=[0, 0, 0], axis_maximum=[350, 350, 330], homed_axes="xyz")))
        with mock.patch.object(ox, "discover", return_value=(actual, evidence)):
            self.assertTrue(ox.check_printer(p, mock.Mock())["prerequisites_satisfied"])
            actual["tools"][0]["max_extrude_cross_section"] = .001
            self.assertFalse(ox.check_printer(p, mock.Mock())["profile_matches_printer"])

    def test_discovery_captures_live_tool_z_reference(self):
        s, c, status, commands = snapshot()
        status["tool reference"] = dict(tool_number=3, extruder="extruder", gcode_z_offset=-.3515)
        p, _ = ox.profile_from_snapshot(s, c, status, commands, "test")
        self.assertEqual(p["tools"][0]["saved_tool_z_offset"], -.3515)

    def test_fallback_tool_mapping_is_flagged(self):
        s, c, status, commands = snapshot()
        s = {k: v for k, v in s.items() if not k.startswith("tool ")}
        p, _ = ox.profile_from_snapshot(s, c, status, commands, "test")
        self.assertEqual(p["discovery"]["tool_mapping_source"], "extruder inference")
        self.assertEqual(p["tools"][1]["select_gcode"], "REVIEW_SELECT_TOOL")

    def test_discover_only_four_get_endpoints(self):
        s, c, status, commands = snapshot()
        client = mock.Mock()
        client.get.side_effect = [dict(state="ready", software_version="test"),
                                  dict(objects=["configfile", "toolhead", "gcode_move", "heater_bed", "extruder", "extruder1"]),
                                  dict(status=status), commands]
        ox.discover(client)
        self.assertEqual([call.args[0] for call in client.get.call_args_list],
                         ["/printer/info", "/printer/objects/list", "/printer/objects/query", "/printer/gcode/help"])

    def test_discovery_shutdown_rejected(self):
        client = mock.Mock()
        client.get.return_value = dict(state="shutdown")
        with self.assertRaises(ox.ProfileError):
            ox.discover(client)
        self.assertEqual(client.get.call_count, 1)

    def test_get_method_and_api_key_header(self):
        client = ox.Moonraker("http://127.0.0.1:7125", "test-placeholder-key")
        client.opener = mock.MagicMock()
        client.opener.open.return_value.__enter__.return_value.read.return_value = b'{"result":{"state":"ready"}}'
        client.get("/printer/info")
        req = client.opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.get_header("X-api-key"), "test-placeholder-key")
        self.assertEqual(client.opener.open.call_args.kwargs["timeout"], 10)

    def test_no_control_endpoints_or_credential_urls(self):
        client = ox.Moonraker("http://127.0.0.1")
        for endpoint in ("/printer/gcode/script", "/printer/restart", "/server/files/upload"):
            with self.assertRaises(ox.ProfileError):
                client.get(endpoint)
        for url in ("ftp://example.org", "http://user:secret@example.org", "http://example.org?apikey=secret"):
            with self.assertRaises(ox.ProfileError):
                ox.Moonraker(url)

    def test_redirects_rejected(self):
        with self.assertRaises(ox.ProfileError):
            ox.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere")

    def test_atomic_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.txt"
            ox.write_new(path, "first")
            with self.assertRaises(FileExistsError):
                ox.write_new(path, "second")
            self.assertEqual(path.read_text(), "first")
            self.assertEqual([p.name for p in path.parent.iterdir()], ["result.txt"])

    def test_cli_preview_generation_and_blocked_draft(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            output = Path(directory) / "preview.svg"
            source = ROOT / "profiles" / "klipper-toolchanger.example.json"
            self.assertEqual(ox.main(["generate", "--profile", str(source), "--preview-only", "-o", str(output)]), 0)
            self.assertTrue(output.is_file())
            self.assertEqual(ox.main(["generate", "--profile", str(source), "-o", str(output.with_suffix(".gcode"))]), 2)
            self.assertFalse(output.with_suffix(".gcode").exists())

    def test_cli_reviewed_artifacts_and_report(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            directory = Path(directory)
            source = directory / "synthetic.json"
            source.write_text(json.dumps(profile()))
            output = directory / "run.01.gcode"
            self.assertEqual(ox.main(["generate", "--profile", str(source), "-o", str(output)]), 0)
            report = ox.read_json(directory / "run.01.report.json")
            self.assertEqual(report["audit"]["rows_checked"], 102)
            self.assertEqual(ox.main(["generate", "--profile", str(source), "-o", str(output)]), 2)

    def test_package_allowlist_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.zip"
            ox.package_release(output)
            with zipfile.ZipFile(output) as bundle:
                names = bundle.namelist()
                self.assertFalse(any("archive/" in n or "output/" in n or ".local." in n for n in names))
                manifest = json.loads(bundle.read("MANIFEST.sha256.json"))
                import hashlib
                for name, hash_value in manifest.items():
                    self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), hash_value)

    def test_calculate_from_report_and_reject_modified_profile(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            p = ox.normalize_profile(profile())
            cells, segments = ox.layout(p)
            report = ox.report_for(p, cells, segments, ox.generate_oxplow_gcode(p))
            source = Path(directory) / "run.report.json"
            source.write_text(json.dumps(report))
            self.assertEqual(ox.main(["calculate", "--report", str(source), "--tool", "0", "--row", "35"]), 0)
            report["profile"]["test"]["direction"] = "low-to-high"
            source.write_text(json.dumps(report))
            self.assertEqual(ox.main(["calculate", "--report", str(source), "--tool", "0", "--row", "35"]), 2)

    def test_literal_macro_dependencies_are_saved_locally(self):
        s, c, status, commands = snapshot()
        c["gcode_macro QUAD_GANTRY_LEVEL"] = dict(gcode="_INNER_CHECK")
        c["gcode_macro _INNER_CHECK"] = dict(gcode="QUAD_GANTRY_LEVEL")
        _, evidence = ox.profile_from_snapshot(s, c, status, commands, "test")
        self.assertIn("gcode_macro _INNER_CHECK", evidence["macros"])

    def test_v2_report_hash_is_checked_before_new_defaults(self):
        p = ox.normalize_profile(profile())
        p["test"].pop("define_objects")
        p["test"].pop("end_retract_owner")
        for t in p["tools"]:
            t.pop("initial_retract")
            t.pop("temperature_command")
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            source = Path(directory) / "old.report.json"
            source.write_text(json.dumps(dict(profile=p,profile_sha256=ox.digest(p))))
            self.assertEqual(ox.main(["calculate", "--report", str(source), "--tool", "0", "--row", "35"]), 0)

    def test_old_report_y_origin_survives_larger_label_defaults(self):
        p = ox.normalize_profile(profile())
        p["test"]["label_scale"] = 1
        cells, _ = ox.layout(p)
        old_y = cells[0]["y"] + 35 * p["tools"][0]["line_step"]
        expected = ox.calculate(p, 0, row=35)
        del p["test"]["label_scale"]
        for t in p["tools"]:
            del t["annotation_line_width"]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "old.report.json"
            source.write_text(json.dumps(dict(version="2.2.1", profile=p, profile_sha256=ox.digest(p))))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ox.main(["calculate", "--report", str(source), "--tool", "0", "--y", str(old_y)]), 0)
            actual = json.loads(out.getvalue())
            self.assertEqual(actual["best_z"], expected["best_z"])
            self.assertEqual(actual["runtime_z_adjust"], expected["runtime_z_adjust"])

    def test_222_report_keeps_annotated_origin_after_patch_only_default(self):
        p = ox.normalize_profile(profile())
        cells, _ = ox.layout(p)
        old_y = cells[0]["y"] + 35 * p["tools"][0]["line_step"]
        expected = ox.calculate(p, 0, row=35)
        del p["test"]["annotations"]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "old.report.json"
            source.write_text(json.dumps(dict(version="2.2.2", profile=p, profile_sha256=ox.digest(p))))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ox.main(["calculate", "--report", str(source), "--tool", "0", "--y", str(old_y)]), 0)
            self.assertEqual(json.loads(out.getvalue())["best_z"], expected["best_z"])

    def test_actual_http_discovery_against_local_mock_server(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading
        s, c, status, commands = snapshot()
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                endpoint = self.path.split("?", 1)[0]
                calls.append(endpoint)
                responses = {"/printer/info": dict(state="ready", software_version="test"),
                             "/printer/objects/list": dict(objects=["configfile", "toolhead", "gcode_move", "heater_bed", "extruder", "extruder1"]),
                             "/printer/objects/query": dict(status=status), "/printer/gcode/help": commands}
                payload = json.dumps(dict(result=responses[endpoint])).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            p, _ = ox.discover(ox.Moonraker(f"http://127.0.0.1:{server.server_port}"))
            self.assertEqual([t["id"] for t in p["tools"]], [3, 9])
            self.assertEqual(len(calls), 4)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


HAS_JINJA = importlib.util.find_spec("jinja2") is not None


class Attr(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


@unittest.skipUnless(HAS_JINJA, "Optional Jinja2 template QA dependency is not installed")
class RuntimeMacroTests(unittest.TestCase):
    def setUp(self):
        import jinja2
        source = (ROOT / "oxplow_runtime.cfg").read_text().split("gcode:\n", 1)[1]
        source = "\n".join(line[4:] if line.startswith("    ") else line for line in source.splitlines())
        self.template = jinja2.Environment(variable_start_string="{", variable_end_string="}").from_string(source)
        self.c = Attr(printer=Attr(max_velocity=300, max_z_velocity=15), heater_bed=Attr(max_temp=120),
                      extruder=Attr(nozzle_diameter=.4, filament_diameter=1.75, min_extrude_temp=170, max_temp=300, max_extrude_only_velocity=30))
        self.printer = Attr(configfile=Attr(settings=self.c), toolhead=Attr(homed_axes="xyz", extruder="extruder", axis_maximum=Attr(z=330), axis_minimum=Attr(z=0)),
                            extruder=Attr(can_extrude=True, temperature=210), heater_bed=Attr(temperature=60),
                            gcode_move=Attr(absolute_extrude=False, absolute_coordinates=True, homing_origin=Attr(z=.02)))
        self.printer["gcode_macro _OXPLOW_CHECK"] = Attr(oxplow_version=ox.VERSION)
        self.params = Attr(STAGE="print", EXTRUDER="extruder", NOZZLE=".4", FILAMENT="1.75", TEMP="210", BED="60",
                           AREA=".093239", RETRACT=".6", LIFT="20", TOL="2", RSPEED="20", SPEED="100", ZSPEED="5")
        self.params["VERSION"] = ox.VERSION

    def render(self):
        def fail(message):
            raise ox.ProfileError(message)
        return self.template.render(printer=self.printer, params=self.params, action_raise_error=fail, action_respond_info=lambda message: "")

    def test_valid_runtime_and_all_stages(self):
        for stage in ("config", "ready", "selected", "print"):
            self.params["STAGE"] = stage
            self.render()

    def test_install_check_does_not_need_homing_heating_or_tool(self):
        self.params = Attr(VERSION=ox.VERSION, STAGE="install")
        self.printer.toolhead.homed_axes = ""
        self.printer.extruder.temperature = 20
        self.render()

    def reference(self):
        self.params.update(TOOL="1", SAVED_Z=".1665")
        self.printer.toolchanger = Attr(tool_numbers=[1], tool_names=["tool T1"], tool_number=1)
        self.printer["tool T1"] = Attr(extruder="extruder", gcode_z_offset=.1665, active=True)
        self.c["tool t1"] = Attr(gcode_z_offset=.1665)

    def test_saved_tool_offset_checked_without_changing_offsets(self):
        self.reference()
        rendered = self.render()
        for cmd in ("SET_GCODE_OFFSET", "SAVE_CONFIG", "G0", "G1", "SET_TOOL_PARAMETER"):
            self.assertNotIn(cmd, rendered)

    def test_changed_runtime_or_stored_z_rejected(self):
        self.reference()
        self.printer["tool T1"].gcode_z_offset = -.3515
        with self.assertRaisesRegex(ox.ProfileError, "offset changed"):
            self.render()
        self.printer["tool T1"].gcode_z_offset = .1665
        self.c["tool t1"].gcode_z_offset = .2
        with self.assertRaisesRegex(ox.ProfileError, "saved tool Z differ"):
            self.render()

    def test_saved_reference_requires_registry_and_active_tool(self):
        self.reference()
        self.printer.toolchanger.tool_number = -1
        with self.assertRaisesRegex(ox.ProfileError, "not active"):
            self.render()
        del self.printer.toolchanger
        with self.assertRaisesRegex(ox.ProfileError, "registry"):
            self.render()

    def test_runtime_rejects_wrong_extruder(self):
        self.printer.toolhead.extruder = "extruder1"
        with self.assertRaisesRegex(ox.ProfileError, "wrong extruder"):
            self.render()

    def test_runtime_rejects_unhomed(self):
        self.printer.toolhead.homed_axes = "xy"
        with self.assertRaisesRegex(ox.ProfileError, "homed"):
            self.render()

    def test_runtime_rejects_cold_or_wrong_bed(self):
        self.printer.extruder.temperature = 170
        with self.assertRaisesRegex(ox.ProfileError, "temperature"):
            self.render()
        self.printer.extruder.temperature = 210
        self.printer.heater_bed.temperature = 40
        with self.assertRaisesRegex(ox.ProfileError, "temperature"):
            self.render()

    def test_runtime_rejects_modes(self):
        self.printer.gcode_move.absolute_extrude = True
        with self.assertRaisesRegex(ox.ProfileError, "G90"):
            self.render()

    def test_runtime_rejects_stale_nozzle(self):
        self.c.extruder.nozzle_diameter = .6
        with self.assertRaisesRegex(ox.ProfileError, "differs"):
            self.render()

    def test_runtime_rejects_wrong_guard_version(self):
        self.params["VERSION"] = "2.0.0"
        with self.assertRaisesRegex(ox.ProfileError, "version mismatch"):
            self.render()

    def test_runtime_rejects_lift_retract_and_speed(self):
        for key, value in (("LIFT", "400"), ("RETRACT", "51"), ("RSPEED", "100"), ("ZSPEED", "20")):
            original = self.params[key]
            self.params[key] = value
            with self.assertRaises(ox.ProfileError):
                self.render()
            self.params[key] = original


if __name__ == "__main__":
    unittest.main()
