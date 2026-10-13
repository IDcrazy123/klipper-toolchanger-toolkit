# Quy trình từ mẫu cá nhân đến công cụ cộng đồng

## 1. Tiếp nhận và xác định phạm vi

Ghi mục tiêu, firmware/plugin và phiên bản, đầu vào, đầu ra, tình huống sử dụng, điều kiện thành công. Tách sự thật đã đọc từ máy khỏi giá trị ví dụ. Với tác vụ thiếu cấu hình máy, vẫn hoàn thành generator, discovery, kiểm tra và tài liệu; không tự nhận file ví dụ là file chạy thật.

## 2. Lưu trữ nguồn và khảo sát

Giữ nguyên file gốc trong archive, tính SHA-256, ghi URL/attribution/license đã biết. Liệt kê file bằng `rg --files`, đọc hướng dẫn có sẵn, kiểm tra Git và thay đổi hiện tại. Lưu bản cấu hình/macro evidence riêng tại máy tính; không đưa API key vào mã hoặc log.

## 3. Tra cứu

Ưu tiên Klipper, Moonraker và repo chính thức của toolchanger. Ghi URL, ngày đọc, phiên bản hoặc commit nếu có, điều đã xác minh và điều chưa xác minh. Trang không truy cập được phải ghi rõ; không khẳng định đã đối chiếu bản online. Khi plugin thay đổi cách áp dụng offset, mở lại mã/tài liệu trước khi chỉnh công thức.

## 4. Phân tích lỗi và thiết kế

Mỗi lỗi cần trigger cụ thể, hành vi trước/sau và cách chứng minh. Tách profile máy khỏi hình học/infill và giao tiếp mạng. Xây hợp đồng macro rõ ràng. Từ chối input vô nghĩa, typo, nonfinite, thiếu tool, vượt bounds/flow/temperature. Thiết kế chặn xuất trước khi có chuyển động nguy hiểm thay vì âm thầm sửa tham số.

## 5. Triển khai

Thay đổi vừa đủ, giữ hàm có nhiệm vụ rõ, không thêm framework không cần thiết. Dùng named heater/extruder; tốc độ profile là mm/s, G-code F là mm/min. Không trộn cú pháp shell/Jinja vào file .gcode. Không xóa/reset offset của máy để làm test có vẻ ổn định.

## 6. Kiểm tra phần mềm

Chạy unit/regression tests theo các lỗi có tác động. Kiểm tra CLI thành công và trường hợp bị từ chối, profile nhiều tool/nozzle, audit chuyển động, preview và mapping kết quả. Ghi số test và môi trường. Test template Jinja có thể dùng Jinja2 ở môi trường phát triển; runtime generator không phụ thuộc thư viện này.

Với runtime guard, kiểm cả trường hợp **macro không được cài**, không chỉ render khi macro đã có. Unknown command có thể là warning rồi tiếp tục; đối chiếu dispatcher/virtual SD đúng phiên bản. Với Z, kiểm annotation độc lập với ramp và không cộng tool offset đã áp bởi máy lần thứ hai. Ghi rõ bằng chứng từ người vận hành khác với bài do agent chạy.

## 7. Kiểm tra máy thật

Chỉ thực hiện với máy/người vận hành được xác định và hành động đã được cho phép. Xác nhận include runtime cfg, home/level/mesh, safe region theo nozzle của từng tool, dock, nhiệt, state retract và cơ chế offset. Bắt đầu một tool, range nhỏ, quan sát trực tiếp, sẵn sàng cancel/emergency stop. Ghi kết quả rồi mới mở rộng nhiều tool. Không biến danh sách này thành yêu cầu xin phép lặp lại khi đã có ủy quyền cụ thể.

## 8. Sửa lỗi và vòng phản hồi

Mỗi báo lỗi dùng template, lấy profile được ẩn thông tin, phiên bản, dòng G-code/log và ảnh first layer nếu người dùng có. Phân biệt lỗi schema, macro, biến đổi tọa độ, cơ khí, flow và Z. Tạo regression test rồi sửa. Không tăng giới hạn Klipper hoặc dùng FORCE_MOVE để né lỗi.

## 9. Cập nhật và phát hành

Cập nhật version/CHANGELOG/migration trước đóng gói. Dùng package allowlist, SHA-256 manifest, chạy test sau khi giải nén. Rà license/attribution trước công bố derivative. Bản chưa test phần cứng phải được đánh dấu experimental. Không đưa profile cá nhân vào gói chung. Chỉ đăng/push khi yêu cầu hiện tại bao gồm công bố.

## 10. Lưu hồ sơ

Mỗi lần thử giữ bộ `.gcode`, `.svg`, `.report.json`, profile, hash, baseline offset/runtime log, nhiệt độ, vật liệu/tấm bàn, ngày, kết quả chọn dòng và thay đổi đã áp dụng. Đặt tên không ghi đè, ví dụ `2026-10-12_machineA_T0_PLA_01`. Bản nguồn cũ lưu riêng; không chạy archive như bản hiện hành.

## Mẫu ghi một phiên thử

```text
Mã phiên / ngày:
Phiên bản toolkit / Klipper / toolchanger:
Profile SHA256 / G-code SHA256:
Tool / nozzle / filament / tấm bàn:
Bed / nozzle / heat soak / mesh:
Baseline offset và nơi lưu offset:
Dòng đẹp nhất / vùng lựa chọn / runtime_z_adjust:
Thay đổi đã áp dụng / kết quả in xác nhận ở range=0:
Vấn đề còn lại / file bằng chứng:
```
