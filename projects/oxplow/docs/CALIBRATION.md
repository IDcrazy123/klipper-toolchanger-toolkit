# Thử và đọc dải Oxplow

## Điều kiện đo

Hiệu chuẩn cơ khí/probe/tool XYZ cơ bản trước. Giữ cùng tấm bàn, vật liệu, nozzle, thermal soak, mesh và baseline offset giữa thử và in thật. Flow hoặc mesh sai cũng tạo gờ/khe; bài thử không tự phân biệt được tất cả nguyên nhân này. Không thay babystep/M221 trong khi dải đang in; nếu đã thay, bỏ kết quả và chạy lại.

Đây là dải serpentine theo từng dòng: Z cố định trên mỗi đường X, đổi tuyến tính trên connector Y. Không phải mỗi đường X có gradient Z và không phải độ phân giải cơ khí thực 0.0001mm. Giữ lượng nhựa danh định không đổi, đánh giá vùng giữa đường tránh ảnh hưởng connector.

## Tọa độ và dấu

Với `N` dòng, index `i=0..N−1`, nominal `h`, range `r`, test_z_adjust `a` (mặc định 0):

```text
low-to-high: Z(i) = h + a − r + 2r × i/(N−1)
high-to-low: Z(i) = h + a + r − 2r × i/(N−1)
runtime delta = Z(best) − h
```

Mẫu hiện hành chỉ in vùng thử nghiệm, không in chữ, tick, purge hay lead-in của generator. Macro start riêng của máy có thể vẫn có purge cần thiết để chuẩn bị nozzle.

**Đứng trước máy, nhìn theo X tăng: đọc các patch từ trái qua phải theo ID tool tăng dần.** Ví dụ chạy T0–T4: trái → phải là T0, T1, T2, T3, T4. Nếu chỉ chạy T2 và T10: trái là T2, phải là T10; không đánh lại thành T0/T1. Một tool chỉ có một patch. SVG có tên tool trên màn hình; tên này không được in. Report có `patches_left_to_right` với tool và tọa độ của từng vùng.

Thứ tự tool theo X và chiều ramp theo Y là hai thông tin riêng. Trong mỗi patch, row 0 là **tâm dòng ở Y thấp nhất** (thường phía trước bàn), dòng cuối ở Y cao nhất (thường phía sau). Mặc định `high-to-low`: Z giảm từ trước ra sau; `low-to-high`: Z tăng. Xác định phía trước/sau theo trục thực tế của máy, không theo ảnh camera có thể đảo hướng. Dòng giữa có index `(N−1)/2`, không có vạch đánh dấu vật lý. Dùng `.report.json` cho index/Y/Z; delta đã gồm test_z_adjust, không cộng a lần nữa.

Ví dụ nozzle 0.4, h=0.24, r=0.06, N=51, high-to-low: dòng 0=0.30, dòng 25=0.24, dòng 50=0.18. Nếu dòng 35 đẹp nhất, Zbest=0.216, delta=−0.024mm; in ở nominal cần nozzle thấp hơn 0.024mm so với baseline lần test.

[Klipper SET_GCODE_OFFSET](https://www.klipper3d.org/G-Codes.html#set_gcode_offset) quy định offset Z dương được cộng vào độ cao nozzle của các chuyển động sau. Vì vậy hiệu chỉnh runtime cho cùng baseline là **cộng delta**, không đảo dấu theo công thức probe. CLI `calculate` xuất câu gợi ý `Z_ADJUST=... MOVE=0`; không gửi câu đó tới máy.

`MOVE=0` tránh di chuyển ngay lập tức; hiệu lực ở chuyển động tuyệt đối Z tiếp theo. Không áp dụng khi nozzle nằm trong dock/chưa biết vị trí. Baseline đã có hiệu chỉnh vật liệu/tấm bàn thì delta phải được cộng vào đúng baseline đó. Gọi Z_ADJUST nhiều lần sẽ cộng dồn.

## Toolchanger và lưu kết quả

Chạy một tool để xác nhận quy trình trước, sau đó test từng tool. Sai lệch chung giữa tất cả tool có thể thuộc global baseline; sai lệch tương đối thuộc tool calibration. Global `SET_GCODE_OFFSET` không tự lưu riêng cho T0/T1 và có thể bị start/tool macros ghi đè.

Không sao chép delta vào `probe.z_offset`, `position_endstop` hoặc `gcode_z_offset` trước khi đọc quy ước của bộ đang cài. Toolchanger có các phiên bản dùng SET_GCODE_OFFSET và các phiên bản dùng move transform riêng. Lưu vào nơi máy đang quản lý per-tool offset theo đúng plugin/version, rồi home/start lại và in xác nhận `ramp_range=0`.

Không tự chạy SAVE_CONFIG/PROBE_CALIBRATE/Z_OFFSET_APPLY_PROBE trong test. Những thao tác này có thể thay calibration khác hoặc restart máy, và kết quả của probe không đồng nghĩa với runtime babystep.

## Đo bằng thước

`--distance` tính từ **tâm** đường ở Y thấp nhất, không từ mép vật liệu. Nếu đo từ mép ngoài, vị trí mép phụ thuộc độ rộng bead thực tế; đổi về tâm hoặc dùng đếm row chính xác. `--y` dùng tọa độ nozzle G-code trong report. Giá trị giữa dòng được nội suy; phần mềm không tuyên bố độ chính xác vật lý tương ứng số chữ số.

Khi không đếm được các đường đã dính liền, đo khoảng cách từ tâm dòng đầu đến vùng đẹp và dùng `calculate --report output/test.report.json --tool 0 --distance 12.0` (thay tool/khoảng cách bằng số đo của bạn). Luôn dùng report đúng bài đã in; bố trí patch-only khác bố trí có chữ cũ. Report 2.2.2 trở về trước vẫn giữ origin cũ khi đọc qua CLI.

Nếu vùng đẹp nhất ở biên, `boundary_result=true`: nghiệm có thể nằm ngoài range. Không tự mở rộng về Z thấp hơn khi chưa kiểm tra baseline. Nếu patch đẹp ở nhiều dòng, chọn vùng giữa và chạy xác nhận nhỏ hơn/range=0. Ghi tool, index, nhiệt, hash, baseline, delta và cách lưu vào hồ sơ phiên thử.
