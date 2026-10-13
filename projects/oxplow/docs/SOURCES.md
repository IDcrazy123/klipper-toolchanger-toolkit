# Nguồn kỹ thuật đã tra ngày 2026-10-12

| Nguồn chính | Điều dùng để đối chiếu |
|---|---|
| [Klipper G-Codes](https://www.klipper3d.org/G-Codes.html) | G90/M83, offset dương cộng vào Z, named heater, TEMPERATURE_WAIT, SAVE/RESTORE state |
| [Klipper Config Reference](https://www.klipper3d.org/Config_Reference.html) | nozzle/filament, extrusion cross section, extrude-only limits |
| [Klipper Command Templates](https://www.klipper3d.org/Command_Templates.html) | Jinja delimiter, action_raise_error, macro được đánh giá trước khi thực thi lệnh của nó |
| [gcode_move.py chính thức](https://github.com/Klipper3d/klipper/blob/master/klippy/extras/gcode_move.py) | implementation offset/mode parsing |
| [extruder.py chính thức](https://github.com/Klipper3d/klipper/blob/master/klippy/kinematics/extruder.py) | kiểm extrusion và effective giới hạn |
| [Moonraker Printer Administration](https://moonraker.readthedocs.io/en/latest/external_api/printer/) | GET info/list/query/gcode help; query qua URL; trạng thái ready |
| [Moonraker Authorization](https://moonraker.readthedocs.io/en/latest/external_api/authorization/) | API key header và quyền truy cập |
| [viesturz/klipper-toolchanger](https://github.com/viesturz/klipper-toolchanger) | tool IDs, extruder mapping, thay đổi offset sang move transform trong changelog |
| [tool.py của plugin](https://github.com/viesturz/klipper-toolchanger/blob/main/klipper/extras/tool.py) | tool_number, T registration, gcode offsets và runtime status |
| [Nhánh Universal Oxplow trên Printables](https://www.printables.com/model/1846885-universal-oxplow-first-layer-z-offset-calibration/files) | File Python online qua trình duyệt, nguồn remix, tác giả và license trang/header |

Các link master/main là nhánh di động, không khóa vào phiên bản đang cài trên máy người dùng. Discovery ghi Klipper version và hash settings; cần ghi thêm commit/version plugin khi vận hành thật. Tài liệu trên không chứng nhận safety của bất kỳ macro cá nhân nào.

## Đối chiếu cho lỗi 2.2.0

- [Klipper gcode.py, commit 7bc4d0946](https://github.com/Klipper3d/klipper/blob/7bc4d0946/klippy/gcode.py): cmd_default chỉ respond_info khi unknown; mux với MACRO không hợp lệ sinh CommandError. Test trực tiếp dispatcher ở PC, không printer I/O.
- [gcode_macro.py cùng commit](https://github.com/Klipper3d/klipper/blob/7bc4d0946/klippy/extras/gcode_macro.py): SET_GCODE_VARIABLE từ chối biến thiếu, chỉ cập nhật variable RAM khi thành công.
- [virtual_sdcard.py](https://github.com/Klipper3d/klipper/blob/7bc4d0946/klippy/extras/virtual_sdcard.py): run_script/CommandError và on_error_gcode của máy. Không suy rộng sang stream từng lệnh Console.
- [KTC-Easy toolchanger.py](https://github.com/jwellman80/klipper-toolchanger-easy/blob/main/klipper/extras/toolchanger.py): ToolGcodeTransform cộng tool offset vào tọa độ cơ khí và khôi phục transform sau pickup. Đã đọc upstream; commit plugin cài thực chưa xác minh, nên không chứng nhận toàn bộ runtime máy chỉ từ nguồn này.

- 2026-10-13: [Klipper G-Codes](https://www.klipper3d.org/G-Codes.html) và [Slicers](https://www.klipper3d.org/Slicers.html), đối chiếu tọa độ offset/retract. Đường chữ 2.2.1 được đánh giá bằng G-code thực và regression; không suy ra Z mới từ tài liệu hoặc ảnh xa.
