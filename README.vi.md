# Bộ công cụ Klipper Toolchanger

Repository chung cho nhiều bộ mã chia sẻ, mỗi dự án nằm trong `projects/<tên>` và có phiên bản, README, test, tài liệu cùng gói phát hành riêng.

Tải bộ hiện hành: [Oxplow trên Printables](https://www.printables.com/model/1846885-universal-oxplow-first-layer-z-offset-calibration/files), [Purge Lines trên Printables](https://www.printables.com/model/1875658-toolchanger-purge-lines-for-klipper-configurable-m/files). CI của nguồn đầu tiên đã đạt trên Python 3.10 và 3.14; các test cũng chạy lại sau khi giải nén ZIP.

- **Oxplow 2.3.2:** chốt nguồn và tạm dừng phát triển. Chỉ in vùng thử first layer, không chữ/vạch. Dữ liệu máy và các phiên thử cũ vẫn giữ local tại workspace gốc.
- **Purge Lines 1.0.0:** chuyển ý tưởng từ macro cá nhân thành builder dùng profile, preview và hợp đồng retract. Đây là bản cộng đồng experimental; hai ảnh là kết quả macro gốc, chưa phải xác nhận lần in bản mới.

Đọc README của dự án trước khi dùng. Sao chép profile ví dụ thành file local, sửa theo máy thật và chỉ xác nhận reviewed sau khi rà. Sinh output, kiểm vùng in/đổi tool/retract trước khi cài. Builder không tự truy cập hoặc chạy máy in.

Python 3.10+; chạy builder không cần dependency ngoài standard library. Khi phát triển, cài `requirements-dev.txt` và chạy `python scripts/run_tests.py`. Không coi bài bị skip là test đã đạt. Không coi test phần mềm là xác nhận cơ khí.

Quy trình chung nằm trong WORKFLOW.md và CONTRIBUTING.md. Khi thêm bộ mã mới, dùng docs/PROJECT_TEMPLATE.md; mã, giấy phép, tài liệu, test, bằng chứng và allowlist phải rõ trước khi chia sẻ. Không đưa profile cá nhân, IP/API key, log máy hoặc output sinh cho máy thật vào Git/ZIP.
