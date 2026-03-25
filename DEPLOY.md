# 🚀 Hướng dẫn Triển khai MediRAG (Full-stack AI Deployment) ✨🌍

Tài liệu này hướng dẫn bạn cách đưa hệ thống **MediRAG** lên môi trường Production hoàn toàn **MIỄN PHÍ** bằng cách kết hợp sức mạnh của Cloud.

---

## 🏗️ 1. Chuẩn bị Hạ tầng (Free Services)

Bạn cần chuẩn bị 3 "mảnh ghép" sau đây:

### 🐘 A. Database (PostgreSQL) - Supabase
1. Truy cập [supabase.com](https://supabase.com/) và tạo project mới.
2. Vào **Project Settings** -> **Database**.
3. Tìm phần **Connection string** (chọn mục *URI*).
4. **Lưu ý:** Chép lại chuỗi này, ví dụ: `postgresql://postgres:[PASSWORD]...`

### ⚡ B. Redis (Broker) - Upstash
1. Truy cập [upstash.com](https://upstash.com/) và tạo Database Redis mới.
2. Chọn Region: **N. Virginia (us-east-1)**.
3. Chép lại **URL** (bắt đầu bằng `rediss://...`).
4. **⚠️ QUAN TRỌNG:** Phải thêm `?ssl_cert_reqs=none` vào cuối URL này để Celery có thể kết nối bảo mật (SSL) thành công.
   - *Ví dụ:* `rediss://default:pass@host:port?ssl_cert_reqs=none`

### ☁️ C. Vector DB - Qdrant Cloud
1. (Bạn đã có) Lấy **Host** và **API Key** từ Qdrant Dashboard.
2. Đảm bảo dùng cổng **443**.

---

## 📦 2. Triển khai lên Render (Web Service)

### Bước 1: Đẩy mã nguồn
Đẩy toàn bộ code lên Github. Đảm bảo có các file: `Dockerfile`, `start.sh`, `requirements.txt`.

### Bước 2: Tạo Web Service
1. Tại [Render Dashboard](https://dashboard.render.com/), chọn **New +** -> **Web Service**.
2. Kết nối tới Github Repo của bạn.
3. Cấu hình:
   - **Runtime:** `Docker` 🐳
   - **Instance Type:** `Free` 🆓

### Bước 3: Điền Biến môi trường (Environment Variables) 🔐
Vào phần **Advanced** -> **Add Environment Variable** và điền đủ 8 biến sau:

| Tên Biến | Mô tả |
| :--- | :--- |
| `DATABASE_URL` | URI lấy từ Supabase (🐘) |
| `REDIS_URL` | URL lấy từ Upstash (⚡) - *Đừng quên tham số SSL* |
| `GROQ_API_KEY` | Groq API Key của bạn (Llama 3.3) |
| `QDRANT_HOST` | Host Qdrant Cloud (ví dụ: `xxx.aws.cloud.qdrant.io`) |
| `QDRANT_API_KEY` | API Key Qdrant Cloud |
| `QDRANT_PORT` | `443` |
| `SECRET_KEY` | Một chuỗi bí mật bất kỳ để tạo Token JWT |
| `ADMIN_PASSWORD` | Mật khẩu dùng để đăng nhập `/admin` |

---

## 🛠️ 3. Cơ chế hoạt động của Monolith Docker

Mã nguồn này đã được tối ưu hóa đặc biệt cho gói **Free** của Render:
- **start.sh:** Khi container khởi động, nó sẽ tự động kích hoạt cả **FastAPI (API)** và **Celery (Worker)** chạy song song.
- **Tối ưu hóa RAM:** Sử dụng **FastEmbed** thay vì các thư viện nặng giúp đảm bảo ứng dụng hoạt động ổn định dưới ngưỡng 512MB RAM. 📉🧠
- **Tiết kiệm:** Bạn chỉ tốn **1 Web Service** (thay vì 2 như các hệ thống thông thường). 🧠⚡

## 🚑 4. Kiểm tra hệ thống
- Sau khi deploy thành công (Trạng thái `Live`), truy cập domain của bạn.
- Thử upload 1 file PDF tại trang Admin. Nếu thấy tiến trình chuyển sang `completed`, chúc mừng bạn đã sở hữu một hệ thống AI RAG chuyên nghiệp! 🏆🏅✨

---
*Phát triển bởi Crowz. 🚑🏁*
