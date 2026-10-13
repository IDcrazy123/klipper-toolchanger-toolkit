# Profile và hợp đồng với máy

## Discovery làm được gì

Đọc effective settings từ `configfile.settings`, cấu hình macro từ `configfile.config`, giới hạn XYZ từ `toolhead`, danh sách lệnh và trạng thái runtime. Ưu tiên registry runtime (kể cả ASSIGN_TOOL), rồi `[tool ...]`, cuối cùng suy đoán ID từ extruder và ghi chưa xác minh. Heater tách khỏi extruder, extruder dùng chung cho nhiều tool, kinematics phi chữ nhật hoặc plugin khác có schema riêng chưa được hỗ trợ.

Không thể suy ra đường đổi tool, kẹp bàn, đáy nozzle vật lý, tham số bắt buộc PRINT_START hay quyền sở hữu retract bằng một snapshot. Từ 2.1.0, registry tool runtime được ưu tiên (gồm ASSIGN_TOOL); heater tách khỏi extruder/extruder dùng chung/kinematics phi chữ nhật vẫn chưa hỗ trợ. Các trường placeholder bắt buộc người vận hành điền. Discovery có thể tạo profile cần sửa tốc độ/temperature nếu giới hạn phần cứng khác mặc định.

## Trường cấp cao

| Trường | Ý nghĩa |
|---|---|
| schema_version | 1; schema JSON nghiêm ngặt, typo/khóa trùng bị từ chối |
| name | Tên local của cấu hình/phiên bản |
| reviewed | false cho discovery/ví dụ; true sau đối chiếu máy |
| machine | Vùng nozzle in an toàn, khoảng Z, lift, nhiệt bàn và giới hạn tốc độ |
| start_gcode / end_gcode | Danh sách dòng lệnh thực; không chèn Jinja hoặc cú pháp shell |
| test | Hình học, chiều ramp, tốc độ, retract, soak và tâm patch |
| tools | Danh sách theo thứ tự in; mỗi ID và extruder duy nhất |
| notes / discovery | Ghi chú, nguồn mapping, phiên bản/hash cấu hình |

## machine

`safe_min=[Xmin,Ymin]` và `safe_max=[Xmax,Ymax]` là vùng tọa độ G-code của **nozzle đang hoạt động**, giao của các vùng tất cả tool có thể in. Phải nằm trên tấm bàn và tránh dock/kẹp. Axis limits discovery là giới hạn toolhead, không tự động là vùng nozzle hợp lệ sau XY offsets/move transforms. Lấy vùng giao bảo thủ và xác nhận trên máy, không chỉ cắt 10mm từ axis limits.

`z_min/z_max` là giới hạn G-code đã đối chiếu với offset/mesh của máy. `travel_z` dùng giữa nét đã in; `toolchange_z` dùng trước/sau chọn tool và trước hành trình XY đầu. Phải thỏa `z_min < travel_z <= toolchange_z <= z_max`. Giá trị 20mm không an toàn phổ quát cho mọi dock. Lift là đích Z tuyệt đối; start/selection phải trả về vị trí mà việc đi tới độ cao này là an toàn. Không đảm bảo lift luôn nâng nếu macro trả về Z cao hơn đích.

`bed_temp`, `bed_max_temp` theo vật liệu và heater config. `max_velocity`, `max_z_velocity` lấy effective printer settings hoặc điền thực tế. Không tăng giới hạn để vượt qua validator. Quy trình làm nóng/heat soak trước homing/level/probe thuộc start macro; `soak_seconds` của generator chỉ chờ sau start, không thay thế thermal policy của máy.

## test

| Trường | Đơn vị / mặc định |
|---|---|
| lines | 51; số lẻ 5–1001 để có tâm chính xác |
| patch_length | 20mm theo X |
| gap | 8mm giữa footprint các patch |
| direction | high-to-low; có low-to-high |
| annotations | false: chỉ patch; true giữ chữ/tick/purge cũ để đối chiếu |
| annotation_speed | 10 mm/s cho chữ/purge/tick/lead-in |
| label_scale | 1.5: chữ 4.5 × 7.5 mm, spacing 6.75 mm |
| print_speed / travel_speed / z_speed | 20 / 100 / 5 mm/s |
| retract_length / retract_speed | 0.6mm filament / 20mm/s |
| soak_seconds | 0; thời gian chờ thêm sau start |
| temperature_tolerance | ±2°C, cửa sổ chờ nozzle và bed |
| center | null tự căn giữa vùng an toàn; hoặc [X,Y] |
| define_objects | false; true để reset/định nghĩa footprint trước adaptive mesh |
| end_retract_owner | generator hoặc end_macro; end_macro giữ tool cuối nóng và không thêm retract trước end |
| end_lift_owner | generator (mặc định) hoặc end_macro; chỉ tool cuối, yêu cầu end_retract_owner=end_macro |

G-code đổi F sang mm/min. Dải Z tối thiểu 0.05mm trong tọa độ G-code chỉ là một ràng buộc dữ liệu; physical clearance còn phụ thuộc baseline offset, mesh và tool transform. Không thể dùng giá trị này để chứng minh nozzle sẽ không chạm bàn.

## tools

`id`, `extruder`, `select_gcode`, `nozzle_diameter`, `filament_diameter`, `temperature`, `min_extrude_temp`, `max_temp` là bắt buộc. `select_gcode` là một macro như `T1` hoặc `SELECT_TOOL T=1`; không dùng `ACTIVATE_EXTRUDER` để thay thao tác pickup vật lý của toolchanger. Chỉ máy single-tool T0/extruder được bỏ selection bằng chuỗi rỗng.

Mỗi tool có thể thêm `nominal_height` (mặc định nozzle×0.6), `ramp_range` (biên ±height×0.25), `line_width` (nozzle×1.1), `line_step` (mặc định diện tích bead / nominal height), `material`, `max_volumetric_flow` (mặc định bảo thủ 8mm³/s), `max_extrude_cross_section`, `max_extrude_only_distance`, `max_extrude_only_velocity`. Khoảng cách mặc định khớp thể tích bead danh định, không mặc định bằng nozzle diameter. Để đối chiếu slicer có thể điền width/spacing thực tế. Flow cap mặc định vẫn cần xác nhận cho hotend/vật liệu. `ramp_range=0` dùng in xác nhận sau hiệu chỉnh.

### Annotation và baseline offset, từ 2.2.0

| Trường mỗi tool | Ý nghĩa |
|---|---|
| annotation_line_width | Rộng nét annotation; mặc định nozzle × 1.5; tối đa nozzle × 2 |
| annotation_height | Chiều cao nhựa chữ/purge/tick; mặc định min(nominal_height, nozzle/2) |
| annotation_z_adjust | Dời Z chữ/purge/tick so với annotation_height; mặc định 0 |
| test_z_adjust | Dời tâm ramp so với nominal_height; mặc định 0, không áp vào annotation |
| saved_tool_z_offset | Số reference đọc từ registry live hoặc null; runtime/validate so baseline, không cộng vào G-code Z |

Z chữ = annotation_height + annotation_z_adjust. Ramp = nominal_height + test_z_adjust ±ramp_range. Cả hai phải trong giới hạn Z/nozzle/travel và ít nhất 0.05 mm theo hệ tọa độ G-code. Offset máy/probe/mesh vẫn do macro/plugin áp dụng. Xem [ANNOTATION_Z.md](ANNOTATION_Z.md).

Diện tích đùn danh định: `h × (w − h) + πh²/4`; E của nét = diện tích × chiều dài XY / diện tích filament. Dùng annotation_height và annotation_line_width cho chữ/purge/tick/lead-in; nominal_height và line_width cho row/connector. E giữa các dòng ramp giữ cố định dù Z thay đổi; không dùng lượng nhựa cố định cho mọi nozzle.

## Hợp đồng macro

Start phải home XYZ, tramming/level và mesh theo thứ tự đúng của máy; chọn/khởi tạo tool cần cho homing; chuẩn bị thermal baseline; không để state dẫn đến di chuyển đầu generator nguy hiểm. Generator không tự G28, QGL hoặc tải mesh default và không reset Z-offset. Mỗi máy phải chọn mesh phù hợp vị trí patch; adaptive mesh chỉ phủ đối tượng slicer cũ có thể không phủ patch test.

Selection phải pickup thành công, kích hoạt đúng extruder, áp XY/Z offsets của tool. Mặc định generator giả định tool không còn retract; nếu start để lại một lượng đã biết, điền `initial_retract` theo từng tool. Generator bù đúng một lần sau kiểm nhiệt tại điểm bắt đầu patch (hoặc purge nếu annotations=true). Không dùng trường này nếu pickup đã tự bù. Guard sau macro xác nhận homing và active extruder nhưng không tự đo có tool thật trên carriage; detection/dock checks thuộc plugin/macro máy.

Purge line ổn định áp suất; retract/unretract giữa các nét cân bằng. Cuối patch mặc định để lại retract `retract_length` và tắt heater. Khi `end_retract_owner=end_macro`, tool cuối không retract/tắt trước end để tránh cộng thêm retract vào macro end tự quản lý. Nếu macro tự quản lý toàn bộ retract, có thể đặt `retract_length=0` nhưng vẫn cần khai báo đúng initial_retract và xác nhận chất lượng travel.

`temperature_command` theo từng tool là `named-heater` (mặc định) hoặc `toolchanger`. Mode thứ hai dùng SET_TOOL_TEMPERATURE T=n TARGET=... khi plugin có command này. Target được đặt trước Tn vì pickup có thể chờ target tại dock; sau selection vẫn đặt lại/kiểm nhiệt. Không tự bật standby đồng loạt cho dock chưa biết.

End phải park/tắt heater theo quy trình máy. Không dùng motor-off tự động. Sau end generator gọi TURN_OFF_HEATERS nếu end đã hoàn tất. Khi lỗi giữa file, end có thể không chạy: CANCEL_PRINT/error handling của máy cần dọn heater và state.

### Chế độ có annotation cũ

Từ 2.3.0, `annotations=false` mặc định. Generator không tạo purge/lead-in/chữ/tick; giới hạn flow/cross section chỉ xét row/connector. Tham số annotation được giữ cho report cũ và chế độ true. Patch trái → phải bố trí theo ID số tăng dần, còn thứ tự in vẫn theo tools trong profile. Xem CALIBRATION.md để đọc mẫu không nhãn.

### Tốc độ annotation

`test.annotation_speed` mặc định 10 mm/s (1–100); dùng cho chữ/purge/tick và travel ngắn trong label. Được kiểm với giới hạn velocity và flow. `print_speed` chỉ điều khiển ramp/connector. Cả hai không thay Z hoặc baseline offset.

Chữ bắt đầu bằng đoạn dẫn 4 mm nối vào chân nét T; đây là phần sacrificial để dòng nhựa ổn định, không phải cạnh glyph. Tăng label_scale thay đổi footprint, cần kiểm SVG và polygon mesh mới. Annotation rộng hơn tăng E riêng, không tăng E ramp hoặc đổi Z máy.

### Bàn giao retract/lift cuối bài

Nếu macro end đã được xác minh retract ở nhiệt đùn trước khi nhấc Z và dock, đặt cả `end_retract_owner` và `end_lift_owner` thành `end_macro`. Generator kết thúc tool cuối tại Z của dòng cuối rồi gọi macro end ngay; tránh nhấc cao khi nozzle còn áp lực. Các tool trung gian vẫn retract/lift theo generator trước đổi tool. Mặc định lift vẫn do generator sở hữu; không bật cờ này cho macro chưa có retract/lift an toàn. Không thêm retract trùng vào máy đã có macro end; PETG vẫn có thể rỉ/tạo tơ dù có retract.
