# Nguồn và trạng thái đối chiếu

Ngày rà soát: 2026-10-12, theo múi giờ Asia/Saigon của người dùng.

Nguồn local đầu phiên: `generate_oxplow_gcode.py`, 26127 byte; archive nguyên trạng: `archive/generate_oxplow_gcode.original-2026-10-12.py`.

SHA-256 bản gốc:

```text
b7702f003d5960167bbdae3e7a928fc8a6f033542a6ee9bc53553803ddcf8e0d
```

Header bản local ghi tác giả “Antigravity AI & Voron Community” và “License: MIT”; đây là khai báo trong file, chưa xác minh nguồn quyền tác giả ngoài file.

Người dùng chỉ định [nhánh Universal Oxplow trên Printables](https://www.printables.com/model/1846885-universal-oxplow-first-layer-z-offset-calibration/files), tác giả hiển thị Công Dương (@CongDuong_4017348). Công cụ web ban đầu không đọc được trang; trình duyệt sau đó mở được Files và nội dung Python liên kết. Trang ghi cập nhật 2026-09-20; file ghi ngày 2026-09-19, khoảng 26kB. Nội dung hiển thị có đúng các lỗi shell mesh, font số 4, rút nhãn tool về chữ số cuối và công thức offset của bản local.

Đối chiếu toàn bộ văn bản sau bỏ CR và trim: 26126 ký tự, checksum FNV-1a 32-bit `e6a973d6` ở cả bản local và nội dung trình duyệt. Đây là so sánh checksum văn bản chuẩn hóa, không phải chứng minh byte-identical hoặc SHA-256 file online. Tải byte trực tiếp bằng HTTP bị 403; byte hash của archive local vẫn là giá trị đã ghi ở trên.

Trang nhánh hiện hiển thị **CC BY 4.0**, trong khi header Python hiển thị **MIT**. Ghi nhận cả hai khai báo, giữ attribution Công Dương, tác giả nguồn Maxim7745 và attribution trong file; không tự giải quyết phạm vi cấp phép từng thành phần. Khi công bố bản sửa, làm rõ giấy phép phần code và phần model/mô tả thay vì giả định tất cả cùng MIT.

Nguồn ý tưởng: [Oxplow Nozzle Z Offset Search — Generic Version](https://www.printables.com/model/777838-oxplow-nozzle-z-offset-search-generic-version), tác giả **Maxim7745**, được nhánh của Công Dương ghi rõ là nguồn remix và Attribution. Chưa mở trực tiếp toàn bộ hướng dẫn gốc; thông tin nguồn/license gốc ở đây lấy từ mục Model origin của nhánh. Bản v2 giữ ý tưởng dải tìm Z, triển khai/hướng dẫn riêng cho Klipper, đổi chiều mặc định và profile hóa máy.

Tài liệu/mã nguồn Klipper, Moonraker và viesturz/klipper-toolchanger dùng để xác minh API và hành vi. Không đóng gói mã plugin của họ vào công cụ; không đồng nhất license của plugin với file generator. Trước phát hành công khai, xác minh license và giữ attribution đúng cho derivative.
