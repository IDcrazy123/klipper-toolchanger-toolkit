# Cài runtime Oxplow 2.3.2 đầy đủ

## File nào khai báo `_OXPLOW_CHECK`?

Macro nằm trong `oxplow_runtime.cfg` ở gốc bộ giải nén. Python chạy trên PC; cfg chạy trên Klipper. Chỉ upload Python hoặc G-code sẽ không cài macro. Dùng generator và cfg cùng version 2.3.2.

Không cần sửa offset tool, probe, Cartographer, dock hoặc PRINT_START để cài runtime. Runtime chỉ kiểm tra/report; không home, gia nhiệt, chuyển động hoặc lưu offset. Biến preflight_token là biến RAM kiểm sự tồn tại, không ghi cấu hình.

## Cài bằng Mainsail hoặc Fluidd

1. Chờ máy rảnh, hết tác vụ đang in/paused. Giải nén `oxplow-2.3.2.zip` trên PC.
2. Mainsail: mở **Machine**, phần **Config Files**. Fluidd: mở **Configuration**, phần file cấu hình. Upload file `oxplow_runtime.cfg` vào thư mục gốc đang chứa `printer.cfg`. Đây là vùng config, không phải G-code Files/Upload & Print.
3. Mở `printer.cfg`. Thêm đúng một dòng ở phần cấu hình bình thường, trên khối tự sinh `#*# SAVE_CONFIG`:

```ini
[include oxplow_runtime.cfg]
```

Nếu chủ máy chọn thư mục con `calibration/`, dòng phải là `[include calibration/oxplow_runtime.cfg]`. Đường dẫn tính tương đối từ file chứa include. Không thêm cả hai. Nếu wildcard đã include cfg này, không include thêm lần nữa.

4. Save & Restart khi máy rảnh. Klipper phải trở lại **Ready**. Nếu file không tìm thấy, kiểm tên và vị trí; trên Linux tên phân biệt hoa/thường. Nếu lỗi macro/config trùng, tìm các include đang nạp cùng file. Nếu lỗi Jinja, dùng lại cfg nguyên vẹn trong ZIP 2.3.2, không dán G-code vào cfg.
5. Mở Console. Nhập lệnh xác nhận chỉ đọc, không chuyển động/không gia nhiệt:

```gcode
_OXPLOW_CHECK VERSION=2.3.2 STAGE=install
```

Kết quả mong đợi: `Oxplow 2.3.2 runtime installed; no motion or heating was performed`. Dấu `_` có thể làm macro không xuất hiện ở panel Macros; điều đó không có nghĩa chưa cài. Có thể kiểm tên bằng `HELP` trong Console.
6. Trên PC, trong thư mục đã giải nén, kiểm profile và runtime bằng GET:

```powershell
python generate_oxplow_gcode.py validate --profile profiles/my-printer.local.json --url http://YOUR_PRINTER:7125
```

Phải có `profile_matches_printer=true`, `prerequisites_satisfied=true`, và profile đã reviewed. Sửa mọi error trước khi nạp file. Chưa home khi validate có thể là warning nếu start đã được rà là sẽ home.
7. Sinh G-code mới bằng 2.3.2, đọc SVG/header/report, upload qua G-code Files và chạy như file bình thường. Khởi đầu T0/một tool, đúng vật liệu/nhiệt, quan sát vùng patch và quy trình prime của máy.

## File mở đầu bằng gì?

Lệnh chạy đầu tiên là:

```gcode
SET_GCODE_VARIABLE MACRO=_OXPLOW_CHECK VARIABLE=preflight_token VALUE=1
```

Trên Klipper có SET_GCODE_VARIABLE/gcode_macro, macro bị thiếu hoặc thiếu biến sinh **CommandError**, ngăn các dòng start tiếp theo trong virtual SD. Sau đó `_OXPLOW_CHECK` kiểm đúng version và cấu hình. `validate --url` kiểm cả sự có mặt của native command và biến này. Đây không phải phương pháp hỗ trợ mọi firmware hoặc cấu hình đã rename/override native commands.

**Không dùng Console để paste cả bài, không stream từng dòng, không xóa guard.** Error ở một lệnh Console không ngăn người gửi lệnh khác tiếp theo. Error/cancel handler riêng của máy có thể tắt heater, park/drop tool theo cấu hình; runtime không thay thế quy trình cancel của máy.

## Sửa lỗi thường gặp

| Thông báo | Nguyên nhân và xử lý |
|---|---|
| `Unknown command:"_OXPLOW_CHECK"` | Cfg chưa được nạp, include sai vị trí, chưa reload hoặc dùng config khác. Kiểm lại bước 2–5; không tiếp tục bài. Bản 2.1 có thể vẫn in sau warning này. |
| `The value '_OXPLOW_CHECK' is not valid for MACRO` | Native preflight 2.2 đang chặn vì chưa nạp runtime. Cài cfg và reload; giữ nguyên lệnh preflight. |
| `Unknown gcode_macro variable 'preflight_token'` | Đang dùng cfg cũ hoặc copy thiếu. Thay bằng cfg đầy đủ 2.3.2. |
| `generator/runtime version mismatch` | Generator/G-code và cfg khác version. Cập nhật cfg, sinh lại G-code; không sửa số version để né kiểm tra. |
| `tool mapping/Z offset changed` | Offset/tool registry đã đổi sau khi sinh profile. Discovery/rà lại, sinh bộ mới; không cộng thêm offset cũ vào Z. |
| `runtime and saved tool Z differ` | Tool đang có chỉnh tạm khác baseline lưu. Xác định lớp offset cần giữ trước khi chạy; không tự SAVE_CONFIG hoặc reset. |
| `XYZ must be homed` / `wrong extruder` / `not active` | Hợp đồng start/tool selection chưa đúng. Rà macro thực của máy, không bỏ guard. |
| Lỗi giữa phiên | Cancel theo quy trình máy, kiểm heater/state trước khi thử lại. PRINT_END có thể chưa chạy. |

## Nâng cấp từ 2.1.0

Giữ cfg cũ ở local để tham khảo. Thay file runtime bằng 2.3.2, kiểm include và reload khi idle. Sinh lại G-code; bố trí mặc định mới không có annotation; file G-code cũ vẫn giữ đường đi cũ. Báo cáo cũ vẫn đọc bằng calculate nếu còn nguyên hash, nhưng không coi nó là dữ liệu của bản in mới.
