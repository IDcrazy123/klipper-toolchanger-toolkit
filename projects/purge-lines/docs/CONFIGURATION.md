# Configuration / cấu hình

All profile fields are required and unknown keys are rejected. Units: millimetres, mm/s, mm³/s and °C. The generated cfg converts speeds to Klipper F in mm/min.

| Field | Meaning |
|---|---|
| schema / reviewed | Schema 1; actual-profile review gate |
| axis | x or y: direction of each long purge stroke and tool-slot ordering |
| purge_area | Clear G-code XY rectangle on usable bed, reviewed for every tool and offsets |
| edge_margin | Space between rectangle edges and bead; must cover nominal half-bead width |
| line_length / line_gap | Preferred stroke length and inter-slot gap; length scales down to fit |
| passes / pass_spacing | 1–6 alternating strokes; spacing must keep nominal beads separate |
| prime_z / travel_z | First-layer and travel coordinates, after machine offsets/mesh |
| wipe_distance | Clearance reserved in both stroke directions; parity chooses wipe direction |
| purge_cross_section | Deposited volume per mm of XY stroke; E = length × area / filament area |
| print_speed / travel_speed / z_speed / retract_speed | Explicit speeds, independent of machine start/end |
| tools[].id / extruder | Unique numeric ID and standard named extruder; sparse IDs supported |
| select_command | One reviewed selection command: Tn or a named adapter with plain parameters |
| nozzle_diameter / filament_diameter | Must match firmware config at purge time |
| max_cross_section / max_volume_rate | Reviewed nozzle/filament/hotend limits; not inferred from printer name |
| entry_recovery | Filament recovery required AFTER tool selection, before purge; 0 if selection already recovers |
| parked_retract / initial_retract | Final retraction for docked and initial printing tool; caller owns recovery |
| standby_temp | Heater target for primed non-initial tools; initial tool stays at requested print temperature |

The runtime reads current coordinates after each selection. Basic coordinate-origin checks cover stroke/wipe/Z endpoints. They do not simulate bed mesh, kinematics, clips, dock motion or external plugin transforms. The reviewed safe rectangle and clearance must account for these. Straight routes within the rectangle and travel to it must be unobstructed.

The builder neither modifies firmware configuration automatically nor raises firmware limits. Native Klipper motion/extrusion checks remain in force. Runtime helpers begin with `_TC_PURGE_`; call only the public `PRIME_LINES` entry after the start macro has prepared the machine.

Sparse slots stay fixed when some tools are unused, making placement predictable. Non-initial used tools prime in ascending numeric ID; initial tool always primes last. Repeated calls reuse the same physical strokes: clear the bed before another call.

Do not add `SAVE_GCODE_STATE` before all tool switches and `RESTORE_GCODE_STATE` after them. On Klipper, restoration also restores base/homing positions, so the final tool may inherit an earlier tool's coordinate state. This implementation deliberately leaves G90/M83/E0 instead.
