# Trợ lý AI Giáo dục THPT

Bộ triển khai GitHub Pages + Render. GitHub Pages chỉ chứa giao diện; Gemini và Groq keys chỉ được lưu ở Render Environment Variables.

## Trước khi đăng công khai

Các Gemini keys cũ từng được nhúng trong HTML. Hãy thu hồi chúng trong Google AI Studio và tạo key mới trước khi deploy. Không đưa key thật vào HTML, GitHub, README, screenshot hoặc tin nhắn.

## 1. Tạo repository GitHub

1. Tạo repository mới trên GitHub. Public repository là cách đơn giản nhất để dùng GitHub Pages miễn phí.
2. Dùng GitHub Desktop để tạo/chọn repository local, rồi chép toàn bộ file trong thư mục dự án này vào thư mục repository.
3. Commit và push lên branch `main`.

Không commit `.env` hay bất kỳ file nào chứa key thật.
File giao diện nguồn ở thư mục gốc phải tên chính xác là `index.html`. File `index.html.txt` không được workflow sử dụng.

## 2. Deploy backend lên Render

1. Đăng nhập Render bằng GitHub, chọn **New** → **Blueprint** và kết nối repository vừa tạo.
2. Render đọc `render.yaml` và tạo web service. Khi được hỏi, nhập `GEMINI_API_KEY` mới, `GROQ_API_KEY`, và `CORS_ALLOWED_ORIGINS`.
3. Với `CORS_ALLOWED_ORIGINS`, nhập origin GitHub Pages của bạn, ví dụ `https://ten-tai-khoan.github.io` (không thêm tên repository hoặc dấu `/` cuối). Nếu dùng custom domain, nhập origin custom domain đó. Không dùng `*`.
4. Deploy xong, lấy URL HTTPS của service, ví dụ `https://ai-gia-su-backend.onrender.com`. Mở URL đó kèm `/health`; cả `geminiApiKeyConfigured` và `groqApiKeyConfigured` phải là `true`.

## 3. Deploy giao diện lên GitHub Pages

1. Trong GitHub repository, mở **Settings** → **Secrets and variables** → **Actions** → **Variables**.
2. Tạo repository variable tên `API_BASE_URL`, giá trị là URL HTTPS của Render, không thêm `/` cuối.
3. Mở **Settings** → **Pages**, chọn **GitHub Actions** làm Build and deployment source.
4. Mở tab **Actions**, chạy workflow **Deploy GitHub Pages**. Workflow tạo `index.html` và điền URL backend; không đưa keys vào trang.
5. Khi workflow thành công, mở link Pages được GitHub hiển thị trong **Settings** → **Pages**.

Mỗi lần push thay đổi lên `main`, workflow sẽ deploy lại. Thay đổi secret thì cập nhật trong Render, không sửa source code.

## Chạy local

Trong PowerShell, nhập key vào biến môi trường của terminal rồi khởi động backend:

```powershell
$env:GEMINI_API_KEY = "KEY_GEMINI_MOI"
$env:GROQ_API_KEY = "KEY_GROQ_CUA_BAN"
& 'C:\Users\eVinhDoraa_\AppData\Local\Programs\Python\Python310\python.exe' '.\ai_proxy.py'
```

Mở URL mà server in ra. Khi chạy local, các API dùng cùng origin nên không cần cấu hình `CORS_ALLOWED_ORIGINS`.

## Lưu ý

- Groq model ID có thể được nhà cung cấp thay đổi/ngừng hỗ trợ. Nếu API trả 400/404, cập nhật `LLAMA_MODEL` hoặc `DEEPSEEK_MODEL` trong `ai_proxy.py` theo model ID đang bật trên tài khoản Groq.
- Render gói miễn phí có thể ngủ khi không hoạt động; lần gọi đầu sau thời gian ngủ sẽ chậm hơn.
- Backend hiện phục vụ người dùng ẩn danh. CORS chỉ giới hạn trình duyệt thông thường, không ngăn script gọi API trực tiếp; trước khi chia sẻ rộng, hãy thêm rate limit hoặc xác thực (ví dụ Cloudflare Turnstile) để tránh người khác dùng hết quota.
- `/health` chỉ trả trạng thái key đã được cấu hình, không bao giờ trả giá trị key.
