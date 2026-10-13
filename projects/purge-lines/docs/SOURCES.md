# Sources

Reviewed 2026-10-13.

- [Original operator macro, pinned source revision](https://github.com/IDcrazy123/All-Config-Voron/blob/7ef1a9fd7338a6275690290820f5aa01249d65e3/config/Printer-Setup/prime-lines.cfg): intent, used-tool temperatures, initial-last order and purge/wipe/retract pattern. Original snapshot kept outside the public repository.
- [Klipper Command Templates](https://www.klipper3d.org/Command_Templates.html): whole-macro evaluation and delayed helper evaluation, state and Jinja syntax.
- [Klipper Status Reference](https://www.klipper3d.org/Status_Reference.html): gcode commands, gcode_move, toolhead, extruder and configfile status.
- [Klipper G-Codes](https://www.klipper3d.org/G-Codes.html): named heater target/wait, extrusion modes and state restore.
- [Klipper gcode_move, reviewed revision 7bc4d0946](https://github.com/Klipper3d/klipper/blob/7bc4d0946/klippy/extras/gcode_move.py): RESTORE_GCODE_STATE restores base/homing positions, modes and factors.
- [viesturz/klipper-toolchanger reference](https://github.com/viesturz/klipper-toolchanger/blob/main/toolchanger.md): tool registry/selection integration; plugin changes must be reviewed for each receiving setup.

Photo credit: Công Dương / IDcrazy123; two photographs expressly supplied for this purge-line project. Code MIT; project documentation and these photos CC BY 4.0. No third-party plugin source is included in release ZIPs.
