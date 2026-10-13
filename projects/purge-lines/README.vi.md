# Purge line cho máy toolchanger dùng Klipper

Bản cộng đồng 1.0.0 là **experimental, chưa in kiểm chứng riêng**. Hai ảnh trong thư mục photos là đường purge của macro gốc do bạn vận hành cung cấp. Builder Python 3.10+ chỉ tạo file local, không tự cài hoặc chạy máy.

## 1. Rà profile máy thật

Sao chép `profiles/printer.example.json` thành `profiles/my-printer.local.json`. Không sửa cờ của file ví dụ để coi đó là preset máy thật. Rà vùng bàn trống, trục chạy nét dài x/y, nozzle/filament, Z, tốc độ, lưu lượng, extruder và lệnh chọn từng tool. Tool ID có thể không liên tiếp.

Ba trường cần đặc biệt khớp với macro/slicer:

- `entry_recovery`: nhựa phải đẩy bù sau khi chọn tool; bằng 0 nếu macro chọn tool đã bù.
- `parked_retract`: lượng rút sau purge của tool không in đầu tiên; lần chọn sau phải bù đúng một lần.
- `initial_retract`: lượng rút cuối của tool in đầu tiên; caller/slicer phải bù đúng một lần trước layer 1.

Sau khi rà cấu hình của chính máy bạn mới đặt `reviewed=true`, rồi chạy:

```text
python build_purge.py validate --profile profiles/my-printer.local.json
python build_purge.py build --profile profiles/my-printer.local.json -o output/prime-lines.cfg
```

Kiểm SVG/report: nét liền đùn nhựa, nét đứt là wipe. Các vị trí tool theo ID tăng dần dọc trục đã chọn; tool không dùng sẽ để trống slot. Bộ sinh chừa chỗ wipe ở hai đầu và rút ngắn nét/E nếu vùng nhỏ; nếu không đủ diện tích thì báo lỗi.

## 2. Cài và nối vào start macro

Lưu bản macro cũ. Upload cfg vừa **sinh từ profile máy thật** vào config của Klipper, thay include/định nghĩa PRIME_LINES cũ để tránh trùng. Thêm đúng một lần trong printer.cfg:

```ini
[include prime-lines.cfg]
```

Save & Restart khi máy rảnh. File `templates/prime-lines.template.cfg` chỉ dùng để đọc cấu trúc, chưa được rà và sẽ từ chối purge.

Start macro hiện tại phải làm home/level/mesh, chuẩn bị nhiệt bàn và offset trước khi gọi. Không chép một PRINT_START chung cho mọi máy. Ví dụ hai tool với T2 in đầu tiên:

```gcode
M220 S100
M221 S100
PRIME_LINES INITIAL_TOOL=2 T0_TEMP=230 T2_TEMP=230
```

Nhiệt độ là ví dụ. Chỉ truyền Tn_TEMP cho tool thực sự dùng; T0 purge trước, T2 purge cuối và được giữ trên đầu máy. Tool selector mặc định có thể là Tn hoặc adapter đã rà như `SELECT_TOOL T=2`. Heater dùng tên extruder, không giả định M104 Tn đã được plugin override.

## 3. In thử và chuyển sang layer 1

Dọn vùng purge, đường di chuyển và dock; thử một tool rồi mới tập tool dùng thật. Macro không nhìn được kẹp bàn, vật cản, model hoặc chuyển động bên trong macro đổi tool.

Khi trả về: tool in đầu tiên còn được chọn, nozzle ở `travel_z`, G90/M83, E=0 và **còn lượng rút initial_retract**. Caller/slicer phải đẩy bù một lần và khôi phục mode/origin E phù hợp trước khi in. Tool khác còn parked_retract, phải được bù đúng khi chọn lại. Heater không tự tắt: tool đầu giữ nhiệt in, tool khác về standby.

Không dùng SAVE/RESTORE_GCODE_STATE bao quanh toàn bộ vòng đổi tool để khôi phục offset của tool trước. Không tự tăng giới hạn Klipper để né lỗi. Xem docs/CONFIGURATION.md, SHARING_REVIEW.md và VALIDATION.md cho hợp đồng, khả năng chia sẻ và giới hạn kiểm tra.
