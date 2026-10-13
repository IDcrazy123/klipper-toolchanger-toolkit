# Thiết kế, kiểm thử và bảo trì

## Các thành phần trong file Python

- `Moonraker` / `discover`: client GET allowlist, timeout, giới hạn payload, không redirect hoặc lệnh printer control.
- `normalize_profile`: schema nghiêm ngặt, kiểu/finite/range, nhiệt, tốc độ, flow, tool IDs.
- `layout`: stroke thật của purge/font/tick/rows/connectors, kiểm footprint với nửa độ rộng bead.
- `generate_oxplow_gcode`: macro contracts, guard, heaters theo tên, G90/M83 sau mỗi selection, lift/XY/descent riêng.
- `audit_gcode`: đọc lại motion/row metadata của phần generator, phát hiện bounds, thiếu dòng và travel thấp.
- `report_for` / `preview_svg` / `calculate`: hồ sơ, bản xem và công thức dấu.
- `package_release`: allowlist file chung và manifest; bỏ profile local, outputs và archive.

Không có daemon/plugin Python nào cần cài vào Klipper. Python chạy ở máy người dùng; .gcode và macro guard là phần Klipper thực thi.

## Chạy kiểm tra

```powershell
python -m py_compile generate_oxplow_gcode.py
python -m unittest discover -s tests -v
python generate_oxplow_gcode.py validate --profile profiles/klipper-toolchanger.example.json
python generate_oxplow_gcode.py generate --profile profiles/klipper-toolchanger.example.json --preview-only -o output/dev-preview.svg
```

Test runtime macro dùng Jinja2 nếu môi trường phát triển có sẵn; được skip khi thiếu. Generator không cần Jinja2. Test mô phỏng state/schema/API không thay test máy thật. Các API tests dùng mock/local response; không liên hệ printer cộng đồng.

Test dispatcher upstream là tùy chọn, không tự tải hoặc liên hệ printer. Đặt `OXPLOW_KLIPPER_SOURCE` trỏ tới checkout local đã rà soát, chứa `gcode.py` và `extras/gcode_macro.py`, rồi chạy unittest. Bộ test import dispatcher/macro của checkout đó với printer/reactor giả; kiểm lỗi thiếu runtime/biến và trường hợp unknown command vẫn tiếp tục. Trong phiên 2.2 đã dùng upstream commit 7bc4d0946; nguồn GPL của Klipper không được chép vào ZIP toolkit. Ghi rõ 80 test core/template + 4 integration khi đã chạy đủ, hoặc ghi số skip nếu thiếu nguồn/Jinja.

## Breaking changes từ v1

Bỏ wizard/preset tự đoán máy và các cờ `--preset`, `--flavor`, `--bed-x`, `--tools` cũ. Hàm Python nhận một profile JSON/dict thay danh sách keyword v1. Chạy không đối số hiển thị lỗi/help, không âm thầm xuất G-code mặc định. Không giữ quảng cáo universal firmware vì chưa có adapter được xác minh.

Chuyển thông số v1 sang profile ví dụ, thay macro hợp đồng thực tế hoặc dùng discover. `print_speed/travel_speed/retract_speed` của v1 là F mm/min; v2 profile là mm/s nên phải chia 60 khi chuyển. Ramp mặc định đổi từ ±40% height xuống ±25%; chiều in mặc định đổi thành high-to-low. Baseline offset không bị reset.

## Giới hạn audit

Audit không phải Klipper interpreter. Không mở rộng macro start/end/selection, không mô phỏng bed mesh, tool transform, pressure advance, homing hay kinematics. Các marker/hình học được kiểm với profile; report chỉ chứng minh một phần file có thể kiểm tĩnh. Runtime guard không phát hiện dock/clip vật lý, calibration cơ khí sai hoặc heat drift sau khi bắt đầu.

`write_new` xuất file qua temporary file + hard link, tránh ghi đè ngay cả khi có tranh chấp. Cần filesystem hỗ trợ hard link (NTFS/ext4 thông thường); nếu không, lệnh sẽ thất bại rõ ràng. Nhóm SVG/report/G-code không phải một giao dịch duy nhất; G-code xuất cuối. Khi I/O lỗi có thể còn companion file, dùng basename mới.

## Nâng cấp

Mỗi sửa schema/thuật toán cập nhật VERSION, macro/version docs, CHANGELOG và regression tests. Khi thay profile hoặc firmware/plugin, tạo bản profile/phiên thử mới và rà lại reviewed. Không dùng kết quả từ hash/profile cũ để tính trên cấu hình đã đổi; report chứa profile chính xác của lần xuất.
