Để lấy file my-tts-key.json (thực chất là tệp tin xác thực tài khoản dịch vụ - Service Account Key) phục vụ cho Google Cloud Text-to-Speech, bạn thực hiện các bước sau:

1. Tạo Dự án (Project) trên Google Cloud Console
Nếu chưa có dự án, hãy truy cập Google Cloud Console, tạo một dự án mới.

2. Kích hoạt API
Tại thanh tìm kiếm của Console, gõ "Text-to-Speech API".

Chọn Cloud Text-to-Speech API và nhấn Enable (Kích hoạt).

3. Tạo Service Account
Vào mục IAM & Admin > Service Accounts.

Nhấn Create Service Account.

Đặt tên cho tài khoản, sau đó nhấn Create and Continue.

Tại phần Grant this service account access to project, chọn vai trò (Role) là Cloud Text-to-Speech API User (hoặc Editor nếu cần quyền rộng hơn).

Nhấn Done.

4. Tải file Key (.json)
Trong danh sách Service Accounts, nhấn vào tài khoản bạn vừa tạo.

Chuyển sang tab Keys.

Nhấn Add Key > Create new key.

Chọn định dạng là JSON và nhấn Create.

Trình duyệt sẽ tự động tải file về máy. Bạn hãy đổi tên file đó thành my-tts-key.json để sử dụng trong code của mình.

Lưu ý quan trọng khi lập trình:
Bảo mật: Không bao giờ upload file này lên các nền tảng công khai như GitHub.

Sử dụng biến môi trường: Trong code Python/JS, thay vì đọc trực tiếp file, hãy thiết lập biến môi trường để bảo mật:

Bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/my-tts-key.json"
Khi đã set biến môi trường này, Google Cloud SDK sẽ tự động nhận diện tài khoản mà không cần truyền đường dẫn file thủ công trong code.


##################################################cài đặt Google Cloud SDK (gcloud)##########################################################

Để cài đặt Google Cloud SDK (gcloud) trên hệ thống, bạn có thể thực hiện theo các cách dưới đây tùy vào hệ điều hành.

1. Trên macOS (Sử dụng Homebrew)
Cách nhanh nhất và dễ quản lý nhất trên macOS là dùng Homebrew:

Bash
# Cài đặt
brew install --cask google-cloud-sdk

# Sau khi cài xong, khởi tạo môi trường gcloud
gcloud init
2. Trên Windows (Sử dụng PowerShell)
Cách tốt nhất là sử dụng trình cài đặt (.exe) chính thức hoặc PowerShell:

Tải bộ cài Google Cloud SDK Installer.

Chạy file .exe và làm theo hướng dẫn cài đặt.

Sau khi cài xong, mở Google Cloud SDK Shell (hoặc PowerShell) và chạy:

PowerShell
gcloud init
3. Trên Linux (Debian/Ubuntu)
Sử dụng các lệnh sau để thêm nguồn và cài đặt:

Bash
# Thêm nguồn phân phối vào apt
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Cài đặt khóa xác thực
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

# Cập nhật và cài đặt
sudo apt-get update && sudo apt-get install google-cloud-sdk

# Khởi tạo
gcloud init
Các bước quan trọng sau khi cài đặt:
Sau khi cài xong, lệnh gcloud init rất quan trọng. Nó sẽ giúp bạn:

Authorize: Đăng nhập bằng tài khoản Google của bạn.

Project Selection: Chọn dự án mặc định trên Google Cloud mà bạn muốn làm việc.

Region/Zone: Thiết lập vùng (Region/Zone) mặc định cho các tài nguyên (thường chọn asia-southeast1 cho Việt Nam để tối ưu độ trễ).

Kiểm tra cài đặt
Sau khi hoàn tất, hãy kiểm tra xem CLI đã nhận diện đúng chưa bằng lệnh:

Bash
gcloud version
Lưu ý cho Coder: Sau khi cài gcloud, nếu bạn dùng VS Code, hãy cài thêm extension "Google Cloud Code". Extension này tích hợp thẳng gcloud vào trình soạn thảo, cho phép bạn quản lý Service Accounts, deploy code và debug ngay trong môi trường VS Code cực kỳ tiện lợi.

################################################### kích hoạt và thiết lập Vertex AI ##################################################
Để kích hoạt và thiết lập Vertex AI (bao gồm cả Cloud Text-to-Speech hoặc các dịch vụ AI khác) qua CLI, bạn cần sử dụng công cụ **Google Cloud SDK (`gcloud`)**.

Dưới đây là các bước trình tự để thiết lập môi trường:

### 1. Xác thực tài khoản

Đảm bảo bạn đã đăng nhập và chọn đúng dự án:

```bash
# Đăng nhập
gcloud auth login

# Thiết lập dự án đang làm việc
gcloud config set project [YOUR_PROJECT_ID]

```

### 2. Kích hoạt dịch vụ Vertex AI (API)

Mặc dù bạn hỏi về Vertex AI, nhưng để sử dụng các tính năng liên quan, bạn cần kích hoạt các API dịch vụ tương ứng.

```bash
# Kích hoạt Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Nếu bạn dùng Text-to-Speech (như câu hỏi trước)
gcloud services enable texttospeech.googleapis.com

```

### 3. Thiết lập xác thực (Authentication) cho CLI

Thay vì sử dụng file JSON thủ công, CLI có cách quản lý tài khoản xác thực rất tối ưu:

```bash
# Kích hoạt tài khoản dịch vụ (Service Account) đã tạo ở bước trước
gcloud auth activate-service-account [SERVICE_ACCOUNT_EMAIL] --key-file=my-tts-key.json

# Cấu hình biến môi trường cục bộ để code của bạn tự nhận diện
export GOOGLE_APPLICATION_CREDENTIALS="[PATH_TO_YOUR_JSON_KEY]"

```

### 4. Kiểm tra cấu hình

Bạn có thể xác nhận mọi thứ đã sẵn sàng bằng cách liệt kê danh sách các dịch vụ đang chạy hoặc kiểm tra cấu hình hiện tại:

```bash
# Kiểm tra cấu hình hiện tại
gcloud config list

# Liệt kê các dịch vụ đã kích hoạt
gcloud services list --enabled

```

---

### Mẹo tối ưu cho Coder

Nếu bạn làm việc với nhiều dự án khác nhau, hãy sử dụng **`gcloud config configurations`** để quản lý các profile khác nhau:

* **Tạo cấu hình mới:** `gcloud config configurations create [PROFILE_NAME]`
* **Chuyển đổi nhanh:** `gcloud config configurations activate [PROFILE_NAME]`

Cách này giúp bạn không cần phải thay đổi biến môi trường thủ công mỗi khi chuyển đổi giữa dự án Dev, Staging hoặc Production.