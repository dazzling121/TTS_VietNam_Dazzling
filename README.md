# TTS Studio Hợp Nhất

TTS Studio là giao diện chạy cục bộ để dùng chung hai bộ tạo giọng đọc Kokoro Vietnamese và VieNeu-TTS. Dự án tập trung vào trải nghiệm đơn giản: nhập văn bản, chọn giọng, chọn thiết bị chạy, tải mô hình khi cần và tạo âm thanh ngay trên máy người dùng.

## Cấu Trúc Dự Án

- `app.py`: giao diện chính bằng Gradio và bộ điều phối các bộ tạo giọng.
- `services/task_queue.py`: hàng đợi tác vụ trong bộ nhớ.
- `services/subtitle_io.py`: nhập phụ đề SRT/VTT và làm sạch kịch bản.
- `services/text_cleaner.py`: làm sạch và chuẩn hóa văn bản tiếng Việt cho TTS.
- `services/export_io.py`: hỗ trợ xuất TXT/SRT/VTT.
- `services/gpu_status.py`: kiểm tra trạng thái NVIDIA GPU.
- `workers/kokoro_worker.py`: tiến trình xử lý Kokoro theo giao thức JSON-lines. Nếu có môi trường chạy Kokoro sẵn thì dùng lại, nếu chưa có thì ứng dụng tự tạo `runtimes\kokoro\.venv`.
- `workers/vieneu_worker.py`: tiến trình xử lý VieNeu theo giao thức JSON-lines. Nếu có môi trường chạy VieNeu sẵn thì dùng lại, nếu chưa có thì ứng dụng tự tạo `runtimes\vieneu\.venv`.
- `voices/user_clones/`: hồ sơ giọng nhân bản do người dùng tạo. Thư mục này không đưa lên GitHub.
- `outputs/`: các file WAV đã tạo. Thư mục này không đưa lên GitHub.
- `logs/`: nhật ký của ứng dụng và các tiến trình xử lý. Thư mục này không đưa lên GitHub.

## Cài Đặt Cho Máy Mới

Nếu vừa tải dự án về, hãy bắt đầu bằng tập lệnh phù hợp với hệ điều hành.

Windows:

```text
START_HERE.bat
```

macOS/Linux:

```bash
chmod +x START_HERE.sh install_unix.sh run_unified.sh STOP_HERE.sh stop_tool_unix.sh
./START_HERE.sh
```

Chỉ kiểm tra máy đang thiếu gì trên Windows:

```powershell
.\START_HERE.bat -CheckOnly
```

Chỉ kiểm tra máy đang thiếu gì trên macOS/Linux:

```bash
./START_HERE.sh --check-only
```

Bộ cài cho người mới sẽ tự nhận hệ điều hành. Windows dùng tập lệnh PowerShell. macOS/Linux dùng tập lệnh shell, sau đó chọn Homebrew hoặc trình quản lý gói Linux phù hợp. Xem thêm hướng dẫn chi tiết trong `SETUP_CHO_NGUOI_MOI.md`.

## Chạy Ứng Dụng

Sau khi cài xong, mở ứng dụng trên Windows:

```powershell
.\run_unified.ps1
```

Hoặc chạy thủ công:

```powershell
cd <thư-mục-dự-án>
.\.venv\Scripts\Activate.ps1
python app.py --server-name 127.0.0.1 --server-port 7870
```

macOS/Linux:

```bash
./run_unified.sh
```

Sau đó mở trình duyệt tại:

```text
http://127.0.0.1:7870
```

## Tắt Ứng Dụng An Toàn

Windows:

```text
STOP_HERE.bat
```

macOS/Linux:

```bash
./STOP_HERE.sh
```

Tập lệnh tắt an toàn sẽ dừng tiến trình xử lý mô hình trước, sau đó dừng giao diện web. Tập lệnh chỉ dừng các tiến trình thuộc đúng thư mục dự án.

## Ghi Chú Quan Trọng

- Ứng dụng chỉ giữ một bộ tạo giọng hoạt động tại một thời điểm để giảm rủi ro thiếu VRAM.
- Khi đổi bộ tạo giọng, ứng dụng sẽ dừng bộ tạo giọng cũ trước rồi mới tải bộ tạo giọng mới.
- Người dùng có thể chọn chạy bằng GPU, CPU hoặc chế độ tự động trong giao diện.
- Trang tạo giọng đọc chính cho phép nhập văn bản và tạo âm thanh trực tiếp, không bắt buộc dùng hàng đợi.
- Kokoro có thể dùng môi trường chạy có sẵn hoặc tự tạo `runtimes\kokoro\.venv`.
- VieNeu có thể dùng môi trường chạy có sẵn hoặc tự tạo `runtimes\vieneu\.venv` bằng gói chính thức `vieneu`.
- Hai dự án nguồn Kokoro và VieNeu không bị sửa trực tiếp.
- Tham số cao độ hiện được lưu trong thiết lập để đồng bộ giao diện, nhưng bộ xử lý nền chưa hỗ trợ chỉnh cao độ riêng.
- VieNeu nhân bản giọng từ file âm thanh mẫu của người dùng.
- Kokoro trong dự án này lưu hồ sơ nhân bản giọng dạng bí danh/cấu hình sẵn dựa trên gói giọng có sẵn.

## Những Phần Đã Kiểm Tra

Kiểm tra ngày 2026-07-05:

- `list_voices` hoạt động với Kokoro và VieNeu.
- Có thể thêm tác vụ thủ công vào hàng đợi.
- Có thể nhập SRT và tạo nhiều tác vụ.
- Kokoro tạo giọng qua ứng dụng và qua API Gradio.
- VieNeu tạo giọng qua ứng dụng.
- Có thể xuất TXT/SRT/VTT.
- Có thể dừng tiến trình xử lý để đưa ứng dụng về trạng thái không có bộ tạo giọng đang chạy.
- Máy chủ Gradio chạy tại `http://127.0.0.1:7870`.

## Danh Sách Chức Năng Đã Hoàn Thành

- [x] Giao diện TTS Studio dạng ba cột.
- [x] Thanh điều hướng bên trái có thể bấm chuyển trang.
- [x] Trang tổng quan có quét CPU/RAM/GPU và đề xuất mô hình/thiết bị.
- [x] Trang tạo giọng đọc trực tiếp, đơn giản.
- [x] Bộ làm sạch văn bản tiếng Việt cho Unicode, nhiễu phụ đề, ngày tháng, thời gian, số, tiền tệ, phần trăm, đơn vị, URL, email và viết tắt phổ biến.
- [x] Khung nhập nội dung có tùy chọn xem văn bản đã làm sạch.
- [x] Hàng đợi tác vụ vẫn được giữ cho quy trình cũ hoặc xử lý theo lô.
- [x] Tạo âm thanh trực tiếp, nghe lại, mở file và tạo lại.
- [x] Bảng điều chỉnh bên phải cho bộ tạo giọng, giọng đọc, cấu hình sẵn, tốc độ, cao độ, âm lượng, cảm xúc và nhiệt độ.
- [x] Bộ chọn GPU/CPU/Tự động.
- [x] Trang nhân bản giọng có tạo bản nghe thử và lưu hồ sơ giọng nhân bản.
- [x] Kho giọng gồm giọng Kokoro, giọng VieNeu và giọng nhân bản của người dùng.
- [x] Tùy chọn xuất TXT/SRT/VTT và mẫu tên file.
- [x] Bảng trạng thái GPU.
- [x] Giữ cơ chế tiến trình xử lý JSON-lines cho Kokoro và VieNeu.
- [x] Chính sách chỉ một tiến trình xử lý hoạt động tại một thời điểm.

## Dọn Dung Lượng Trước Khi Đưa Lên GitHub

Các thư mục sau là dữ liệu tự sinh hoặc dữ liệu cá nhân, không nên đưa lên GitHub:

- `.venv/`
- `runtimes/`
- `downloads/`
- `tools/ffmpeg/`
- `logs/`
- `outputs/`
- `voices/user_clones/`
- `backups/`
- `__pycache__/`
- `model_paths.json`

Các mục này đã được khai báo trong `.gitignore`.
