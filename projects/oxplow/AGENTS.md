# Quy tắc riêng cho Oxplow

Trong workspace, áp dụng AGENTS.md ở thư mục cha. Với gói giải nén độc lập, dùng docs/WORKFLOW.md làm quy trình. Đọc README.md và docs/CONFIGURATION.md trước sửa profile/schema. Không tự gửi lệnh tới máy, tự đổi reviewed trên ví dụ hoặc đóng gói dữ liệu local.

Khi thay đổi generator, chạy từ thư mục này:

```powershell
python -m unittest discover -s tests -v
python generate_oxplow_gcode.py validate --profile profiles/klipper-toolchanger.example.json
```

Khi thay đổi `_OXPLOW_CHECK`, kiểm tra render Jinja theo delimiter Klipper và các đường từ chối trạng thái. Giữ các lần gọi guard tách khỏi macro start/tool để đọc trạng thái sau khi macro trước hoàn tất. Không dùng SAVE/RESTORE_GCODE_STATE để âm thầm khôi phục tool offset khi tool khác đang được chọn.

Generator phải bảo toàn lượng nhựa danh định qua ramp; purge/label/tick có E theo hình học, retract/unretract cân đối giữa các nét, retract cuối patch được mô tả trong hợp đồng chọn tool. Không xuất mặc định một file G-code chạy được khi người dùng chưa cung cấp profile đã rà soát.
