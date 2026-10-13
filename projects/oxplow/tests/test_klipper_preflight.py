"""Optional integration against a local checkout of Klipper, with no printer I/O.

Set OXPLOW_KLIPPER_SOURCE to a directory containing gcode.py and
extras/gcode_macro.py from the reviewed Klipper revision. No downloads occur here.
"""
import contextlib
import importlib.util
import os
from pathlib import Path
import unittest
from unittest import mock


SOURCE = os.environ.get("OXPLOW_KLIPPER_SOURCE")


@unittest.skipUnless(SOURCE, "Set OXPLOW_KLIPPER_SOURCE for upstream dispatch integration")
class KlipperPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name, filename):
            spec = importlib.util.spec_from_file_location(name, Path(SOURCE) / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        cls.gcode = load("oxplow_upstream_gcode", "gcode.py")
        cls.macro = load("oxplow_upstream_macro", "extras/gcode_macro.py")

    def setUp(self):
        printer = mock.Mock()
        printer.get_start_args.return_value = {}
        printer.get_reactor.return_value.mutex.return_value = contextlib.nullcontext()
        self.dispatch = self.gcode.GCodeDispatch(printer)
        self.reached_start = []
        self.messages = []
        self.dispatch.register_output_handler(self.messages.append)
        self.dispatch.register_command("PRINT_START", lambda gcmd: self.reached_start.append(True))
        # A normal printer has other start/end/tool macros, even when Oxplow is absent.
        self.dispatch.register_mux_command("SET_GCODE_VARIABLE", "MACRO", "PRINT_START", lambda gcmd: None)
        self.dispatch._handle_ready()
        self.probe = "SET_GCODE_VARIABLE MACRO=_OXPLOW_CHECK VARIABLE=preflight_token VALUE=1"

    def install(self, variables):
        runtime = self.macro.GCodeMacro.__new__(self.macro.GCodeMacro)
        runtime.variables = variables
        self.dispatch.register_mux_command("SET_GCODE_VARIABLE", "MACRO", "_OXPLOW_CHECK", runtime.cmd_SET_GCODE_VARIABLE)
        return runtime

    def test_old_unknown_macro_only_warns_and_start_runs(self):
        self.dispatch.run_script("_OXPLOW_CHECK\nPRINT_START")
        self.assertEqual(self.reached_start, [True])
        self.assertTrue(any('Unknown command:"_OXPLOW_CHECK"' in message for message in self.messages))

    def test_missing_runtime_native_probe_raises_before_start(self):
        with self.assertRaises(self.gcode.CommandError):
            self.dispatch.run_script(self.probe + "\nPRINT_START")
        self.assertEqual(self.reached_start, [])

    def test_old_runtime_missing_probe_variable_raises_before_start(self):
        self.install({"oxplow_version": "2.1.0"})
        with self.assertRaisesRegex(self.gcode.CommandError, "Unknown gcode_macro variable"):
            self.dispatch.run_script(self.probe + "\nPRINT_START")
        self.assertEqual(self.reached_start, [])

    def test_installed_probe_changes_only_volatile_token(self):
        runtime = self.install({"oxplow_version": "2.2.0", "preflight_token": 0})
        self.dispatch.run_script(self.probe)
        self.assertEqual(runtime.variables, {"oxplow_version": "2.2.0", "preflight_token": 1})
        self.assertEqual(self.reached_start, [])


if __name__ == "__main__":
    unittest.main()
