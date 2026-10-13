# CHANGELOG

## 2.3.2 — 2026-10-13

- Siết audit E nominal của row/connector ngay cả dưới flow cap, có dung sai theo làm tròn XY/E. Kiểm modal feed, XY/Z/E-only velocity và thành phần Z của mixed move.
- 96 regression tests đạt; thêm trường hợp sai E/tốc độ, connector nozzle .15/filament3.5 và feed kế thừa. Phần sinh chuyển động không đổi so với2.3.1.
- README và hướng dẫn Printables còn ba bước cài → sinh → in/đọc. Chi tiết cấu hình, lỗi, nguồn và lịch sử ở tài liệu riêng. Bằng chứng/config/kết quả máy cá nhân giữ local, không nằm trong gói chia sẻ.

## 2.3.1 — 2026-10-13

- Thêm test.end_lift_owner, mặc định generator. Với macro end đã retract/lift an toàn, end_macro bàn giao ngay ở Z in cuối, tránh lift trước retract. Yêu cầu end_retract_owner=end_macro; chỉ áp dụng tool cuối.
- Giữ retract/lift của tool trung gian và hợp đồng macro riêng. 92 tests đạt; không tự tăng retract hoặc sửa offset.

## 2.3.0 — 2026-10-13

- Mặc định annotations=false: chỉ ramp, bỏ glyph/tick/purge/lead-in của generator; prime của macro máy giữ hợp đồng riêng. Chế độ true giữ cho đối chiếu legacy.
- Patch trái → phải theo ID số tăng dần, thứ tự in vẫn theo tools. Header/report/SVG ghi mapping; tên chỉ có trên preview. Hướng dẫn phân biệt tool theo X và ramp theo Y.
- Sửa float equality gây retract/lift thừa giữa row/connector cùng điểm nối. 90 tests đạt; report <=2.2.2 giữ origin cũ qua calculate.

## 2.2.2 — 2026-10-13

- Annotation width riêng, default nozzle×1.5; glyph scale1.5 và lead-in nối chữ T. E ramp không thay đổi.
- 84 tests đạt, gồm width/lead-in/bounds/flow và tương thích Y origin report cũ.

## 2.2.1 — 2026-10-13

- Sắp digit thành connected trails giữ nguyên các cạnh; T stem trước crossbar. Travel ngắn giữa label chậm, không retract/lift; hành trình khác vẫn lift.
- Annotation speed10mm/s độc lập ramp. 79 tests đạt, gồm dispatcher upstream và regression glyph/travel.

## 2.2.0 — 2026-10-12

- Native SET_GCODE_VARIABLE preflight bắt macro/biến thiếu trước start; Unknown command đơn lẻ không đủ bảo đảm file dừng. Runtime/generator kiểm version tương thích.
- Tách annotation height/Z/E khỏi ramp; saved tool offset chỉ là reference guard, không cộng vào Z lần nữa.
- INSTALL_KLIPPER.md có vị trí cfg, include/reload, Console verification và xử lý lỗi. 70 core/template tests và4 dispatcher tests đạt.

## 2.1.0 — 2026-10-12

- Discovery ưu tiên tool registry, hỗ trợ mapping ASSIGN_TOOL, ghi evidence local và cảnh báo hợp đồng chưa review.
- Initial retract, temperature command và end_retract_owner theo profile; object footprint phục vụ mesh macro. 58 tests đạt.

## 2.0.0 — 2026-10-12

- Toolkit CLI discover/validate/generate/calculate/package, profile schema có rà soát, SVG/report/hash, audit bounds/extrusion/temperature và sharing allowlist.
- Ví dụ chưa reviewed; không gửi lệnh, upload, scan mạng hoặc lưu offset từ public discovery/generator.
