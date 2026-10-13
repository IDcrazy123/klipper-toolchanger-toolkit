# Phát hành từ cá nhân ra cộng đồng

## Gói chia sẻ

```powershell
python -m unittest discover -s tests -v
python generate_oxplow_gcode.py package -o dist/oxplow-2.3.2-candidate.zip
```

Gói gồm Python standalone, macro guard, profile ví dụ chưa reviewed, hướng dẫn, test và MANIFEST.sha256.json. Không chứa profile lấy từ máy, API key, macro evidence, output hoặc file archive. Không tự upload/đăng Printables. Đây là candidate để review; chức năng package không chứng nhận phần cứng hay tự chọn giấy phép phát hành.

Giải nén vào thư mục mới, kiểm manifest, chạy test và preview tại thư mục đó. Giữ attribution Công Dương, Maxim7745 và attribution trong header nguồn. Trang Printables hiện ghi CC BY 4.0, header Python ghi MIT; làm rõ phạm vi giấy phép từng thành phần trước khi công bố derivative. Chi tiết đối chiếu ở PROVENANCE.md.

## Điều kiện ghi nhãn một profile được hỗ trợ

Ghi máy, kinematics, Klipper/toolchanger version, nozzle/filament, vùng in, macro contracts, cơ chế lưu offset và test thực tế. Kiểm single-tool T0, single nonzero tool, nhiều tool, cancel/failure và heat policy trên phần cứng được phép. Người khác vẫn cần discovery/profile riêng, không dùng profile của bạn như thông số chung.

Chưa có thử phần cứng thì mô tả experimental/software-tested. Sau thử có log/ảnh và điều kiện đo, cập nhật danh sách hỗ trợ; không khái quát một Voron thành mọi StealthChanger hay mọi Klipper.

## Nội dung mô tả Printables đề xuất

```text
Oxplow Klipper Toolkit 2.3.2 (experimental; software-tested; patch-only layout; printer-specific hardware verification required)
Python 3.10+, no runtime pip dependencies.
Read each printer's configuration via Moonraker; review its profile before exporting.
Generates first-layer serpentine Z-search patches per tool, SVG preview and row/offset report.
Requires the included Klipper runtime macro plus validated start/end/tool macros.
No automatic printer commands, upload or persistent offset writes.
This version targets Klipper. Hardware compatibility depends on printer-specific macro contracts.
```

Chèn link nguồn/remix và license đã xác minh trước khi đăng. Đưa cả `.py`, `.cfg`, profile ví dụ và docs vào ZIP; chỉ tải file Python sẽ thiếu guard/hướng dẫn cần thiết.
