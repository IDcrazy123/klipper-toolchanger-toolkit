# Bằng chứng kiểm tra phần mềm — 2.3.2

96 regression tests đạt trên Windows/Python3.14, gồm 4 integration tests với dispatcher upstream Klipper commit7bc4d0946. Generator đặt mục tiêu Python3.10+; chưa chạy matrix3.10–3.13. Gói giải nén được kiểm manifest SHA256 và chạy lại toàn bộ test.

## Phạm vi đã kiểm

- Profile tổng hợp được đánh dấu rõ trong tests: một/nhiều tool, ID không liên tiếp, thứ tự vị trí tăng theo ID nhưng giữ thứ tự macro; examples phát hành vẫn reviewed=false.
- Patch-only không có purge/glyph/tick/lead-in. Row/connector đùn liên tục, không retract/lift thừa vì float roundoff. Retract đầu và ownership cuối kiểm độc lập.
- Hai chiều ramp, range=0, bounds/footprint, nozzle/filament khác nhau, E nominal giữ cố định và annotation legacy riêng. Report cũ giữ Y origin; hash bị sửa bị từ chối.
- Audit từ chối E ramp sai dù vẫn dưới flow cap; kiểm feed kế thừa, XY/Z/E-only velocity và Z component khi phối hợp. Có connector nhỏ nozzle .15/filament3.5 để kiểm dung sai làm tròn.
- Guard: macro/biến thiếu phải dừng trước start. Dispatcher thật kiểm khác biệt giữa Unknown command và CommandError; không thử lỗi này bằng chuyển động trên máy.
- Discovery chỉ dùng GET allowlist; kiểm duplicate JSON, nonfinite, typo, macro placeholder, URL/redirect và output không ghi đè. Package không chứa profiles cá nhân, output, archive hay control helpers.

## Kiểm tra phần cứng theo từng máy

Test phần mềm không chứng nhận cơ khí, chất lượng first layer hoặc mọi firmware/plugin. Mỗi máy cần profile/macro/offset contract được rà, thử tool đơn trước rồi nhiều tool, kiểm nhiệt, retract, toolchange và xử lý lỗi.

Cấu hình, macro evidence, G-code/report/ảnh/log và đánh giá in cá nhân giữ local. Khi ghi nhận một phiên thực tế, lưu version/hash, vật liệu, baseline, state cuối và phản hồi người vận hành theo WORKFLOW.md. Không chọn offset từ ảnh xa hoặc suy ra khe nozzle–bàn từ tọa độ firmware.

## Lặp lại kiểm tra

```text
python -m unittest discover -s tests
```

Đặt OXPLOW_KLIPPER_SOURCE tới checkout upstream đúng commit khi chạy dispatcher tests. Chạy tại thư mục giải nén, kiểm MANIFEST.sha256.json và preview trước khi chia sẻ. Số test nêu trên bao gồm dispatcher, không phải kết quả khi các bài integration bị skip.
