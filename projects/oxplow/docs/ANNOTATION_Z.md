# Chế độ annotation legacy và Z ramp

Mặc định từ2.3.0: test.annotations=false, chỉ in patch. Cách đọc hiện hành ở CALIBRATION.md. Các trường dưới giữ cho report cũ hoặc khi chủ động bật annotations=true; không cần bật để hiệu chuẩn first layer.

## Ba lớp độc lập

1. Baseline probe/tool/mesh/runtime do máy áp dụng. saved_tool_z_offset là reference để guard kiểm thay đổi; không cộng vào G-code Z lần nữa. Z-Offset0 trên UI không chứng minh mọi stored offset bằng0.
2. Annotation Z=annotation_height+annotation_z_adjust. E dùng annotation_height và annotation_line_width riêng; không dùng Z thử để tăng/giảm E. Default height=min(nominal_height,nozzle/2), width=nozzle×1.5.
3. Ramp Z=nominal_height+test_z_adjust±ramp_range. E theo nominal_height và line_width, cố định giữa các dòng. Tham số annotation không tham gia công thức kết quả.

Ví dụ tổng hợp nozzle .4, nominal .24, range .04, test_z_adjust=-.02: ramp high-to-low đi .26→.18, tâm .22. Nếu chọn tâm, runtime delta=.22−.24=-.02; delta đã gồm test_z_adjust, không cộng lại. Đây là ví dụ toán học, không phải profile dùng trên máy thật.

## Legacy layout

Annotation dùng glyph nối thành trails, annotation_speed mặc định10mm/s, label_scale1.5 và lead-in nối chữ T. Footprint/flow/bounds xét width/height từng nét. Travel label ngắn tối đa5mm ở cùng Z; hành trình khác retract/lift. Layout legacy giữ thứ tự tools; patch-only dùng ID số tăng từ trái→phải. CLI calculate --report giữ Y origin của report cũ nếu hash nguyên vẹn.

## Khi baseline chưa rõ

Discovery ghi registry/evidence bằng GET; profile cần rà macro/version thực, nhất là plugin dùng transform riêng. Không tự giảm Z từ ảnh hoặc tăng initial_retract để che lỗi. Nếu xét chất lượng, phân biệt gap/flow/nozzle/bàn/prime và giữ điều kiện đo. Tọa độ firmware không phải số đo khe nozzle–bàn. Không tự SAVE_CONFIG, probe calibration hoặc SET_GCODE_OFFSET từ generator.
