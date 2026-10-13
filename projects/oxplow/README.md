# Oxplow cho Klipper

Python 3.10+, không cần pip cho generator. Sinh G-code first layer, SVG và report Z cho profile riêng của từng máy. Mẫu mặc định chỉ có vùng thử, không in chữ hoặc vạch phụ. Offset đã lưu do máy áp dụng; generator không cộng lại và không tự lưu hiệu chỉnh.

## 1. Cài runtime

Giải nén ZIP hiện hành. Upload `oxplow_runtime.cfg` vào thư mục config, cùng cấp `printer.cfg`, rồi thêm:

```ini
[include oxplow_runtime.cfg]
```

Save & Restart khi máy rảnh. Trong Console chạy:

```gcode
_OXPLOW_CHECK VERSION=2.3.2 STAGE=install
```

Chỉ tiếp tục khi thấy `runtime installed`. Python và cfg phải cùng bộ. Nếu lỗi/thiếu macro, xem [hướng dẫn cài đầy đủ](docs/INSTALL_KLIPPER.md).

## 2. Tạo G-code

Mở terminal trong thư mục giải nén. Thay URL minh hoạ bằng Moonraker của máy bạn:

```text
python generate_oxplow_gcode.py discover --url http://192.0.2.10:7125 -o profiles/my-printer.local.json
```

Sửa JSON theo máy: macro start/end/chọn tool, vùng XY an toàn, vật liệu/nhiệt, nozzle và trạng thái retract/lift. Chỉ đặt `reviewed=true` sau khi rà profile thật. Không dùng profile ví dụ để in. [CONFIGURATION.md](docs/CONFIGURATION.md) giải thích các trường và hợp đồng macro.

```text
python generate_oxplow_gcode.py validate --profile profiles/my-printer.local.json --url http://192.0.2.10:7125
python generate_oxplow_gcode.py generate --profile profiles/my-printer.local.json -o output/test.gcode
```

Sửa lỗi validation rồi kiểm SVG/header trước khi upload G-code. Đầu ra gồm `.gcode`, `.svg`, `.report.json`; không ghi đè file cũ. Discovery chỉ đọc máy; công cụ không tự upload hoặc bắt đầu in.

## 3. In và đọc kết quả

Dọn bàn, kiểm vật liệu, bắt đầu với một tool và in file qua Mainsail/Fluidd. Macro start của máy có thể có prime riêng.

- **Trái → phải (+X): ID tool tăng dần**, ví dụ T0 → T1 → T2 → T3 → T4. Nếu chỉ chạy T2/T10 thì trái T2, phải T10. Thứ tự in vẫn theo tools trong profile. SVG/report ghi mapping; tên trên SVG không được in.
- **Trong một patch:** row 0 ở Y thấp nhất, thường phía trước. Mặc định Z giảm về Y cao/phía sau; `low-to-high` thì tăng. Dòng giữa là `(lines−1)/2`; không có tick vật lý.
- Chọn vùng nhẵn, các đường dính đều, không khe/gờ; tránh chỗ quay đầu. Dùng report đúng lần in.

```text
python generate_oxplow_gcode.py calculate --report output/test.report.json --tool 0 --row 35
```

Nếu khó đếm dòng, thay `--row 35` bằng `--distance 12.0`: khoảng cách mm từ tâm dòng Y thấp nhất đến vùng đẹp. Số dương nâng nozzle, số âm hạ. Lưu theo quy trình offset của máy rồi in xác nhận `ramp_range=0`. [CALIBRATION.md](docs/CALIBRATION.md) có cách đo, dấu và xử lý kết quả ở biên.

## Tra cứu và phát triển

Cài/lỗi runtime: [INSTALL_KLIPPER.md](docs/INSTALL_KLIPPER.md). KTC/prime: [KTC_INTEGRATION.md](docs/KTC_INTEGRATION.md). Quy trình sửa/chia sẻ: [WORKFLOW.md](docs/WORKFLOW.md). Bằng chứng test: [VALIDATION.md](docs/VALIDATION.md). Lịch sử và nguồn nằm riêng trong [CHANGELOG.md](CHANGELOG.md), [SOURCES.md](docs/SOURCES.md), [PROVENANCE.md](docs/PROVENANCE.md).

```text
python -m unittest discover -s tests
python generate_oxplow_gcode.py package -o dist/oxplow-2.3.2.zip
```

Gói chia sẻ dùng allowlist; profile/API key/kết quả máy cá nhân giữ local. Test phần mềm không thay thế kiểm tra cơ khí và chất lượng bản in.
