# Hợp đồng toolchanger, prime và end

## Offset và mapping

Với các plugin KTC/KTC-Easy/toolchanger, đọc đúng source/version đang cài và đối chiếu registry/tool ID/extruder qua discovery. Một số phiên bản dùng move transform; saved_tool_z_offset chỉ là reference guard, không cộng lại vào Z của generator. Không suy ra cách áp offset từ tên máy hoặc tên plugin. Nguồn upstream ở SOURCES.md; evidence máy cá nhân giữ local.

## Start và chọn tool

start_gcode/end_gcode/select_gcode phải là lời gọi thật mà máy hỗ trợ. Không có giao thức PRINT_START hoặc bộ tham số nhiệt chung cho mọi máy. Điền placeholder theo macro của bạn; giữ reviewed=false khi còn chưa rõ contract. Xác minh home/level/mesh, prime, detection/dock, giới hạn và active extruder sau selection.

## Mesh footprint

Nếu macro mesh đọc exclude-object, bật test.define_objects=true khi EXCLUDE_OBJECT_DEFINE có sẵn. Generator định nghĩa polygon trước start; chế độ mặc định bao các patch. Chế độ annotation legacy bao thêm nét phụ. Macro máy sở hữu homing/mesh; không tự chạy mesh lần hai trong generator.

## Retract còn lại sau prime

initial_retract là lượng retract đã biết còn lại trên từng tool sau start/pickup. Generator hồi đúng một lần tại điểm bắt đầu patch. Nếu pickup đã tự hồi, để0; nếu chưa xác định state, rà macro/evidence thay vì tăng bù theo cảm giác. State của tool đầu và tool được prime rồi park có thể khác nhau.

## End và lift

Nếu macro end tự retract khi nozzle còn nóng, đặt test.end_retract_owner=end_macro để generator bàn giao retract/heater tool cuối. Nếu macro đó cũng lift an toàn trước dock, đặt thêm test.end_lift_owner=end_macro: gọi end ngay sau dòng cuối, tránh generator lift trước retract. Mặc định lift do generator; chỉ đổi ownership sau khi rà macro thật. Tool trung gian vẫn retract/lift trước đổi tool. TURN_OFF_HEATERS dọn target sau end thành công; cancel/error policy vẫn thuộc máy.

## Nhiệt và kiểm live

Pickup hook có thể chờ target của tool đang đỗ, nên generator đặt target trước selection rồi kiểm nhiệt sau. Nếu plugin có SET_TOOL_TEMPERATURE, dùng temperature_command=toolchanger; mặc định named-heater dùng tên extruder thật. Standby/heat soak thuộc macro máy.

```text
python generate_oxplow_gcode.py validate --profile profiles/my-printer.local.json --url http://YOUR_PRINTER:7125
```

Lệnh này chỉ đọc mapping/limits/capabilities/guard version; không upload/restart hay chứng nhận chuyển động macro. Cài runtime theo INSTALL_KLIPPER.md rồi kiểm lại khi máy đã Ready.
