# 🤖 MediRAG — AI Medical Knowledge Assistant 🏥✨

**MediRAG** là một giải pháp Chatbot hỏi đáp thông minh dành cho lĩnh vực Y tế, sử dụng kỹ thuật **RAG (Retrieval-Augmented Generation)** tiên tiến để cung cấp thông tin chính xác dựa trên kho tài liệu nội bộ của bạn.

![MediRAG Branding](https://img.shields.io/badge/MediRAG-Modern--RAG-4fd1c5?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Qdrant](https://img.shields.io/badge/Qdrant-Cloud-ff4b4b?style=for-the-badge&logo=qdrant)
![Groq](https://img.shields.io/badge/Groq-Llama_3.3-f3a000?style=for-the-badge)
![FastEmbed](https://img.shields.io/badge/FastEmbed-Lightweight-blueviolet?style=for-the-badge)

## ✨ Tính năng nổi bật

- ⚡ **Hỏi đáp Thời gian thực:** Sử dụng kiến trúc SSE (Server-Sent Events) giúp câu trả lời hiển thị mượt mà từng chữ.
- ☁️ **Cloud Native:** Tích hợp trực tiếp với **Qdrant Cloud** (AWS N. Virginia) cho khả năng tìm kiếm vector tốc độ cao.
- 📦 **Monolith Docker:** Chạy cả API và Celery Worker trong cùng một Container, tối ưu hóa cho việc triển khai miễn phí trên Render/Koyeb.
- 📊 **Admin Dashboard:** Giao diện quản trị hiện đại để theo dõi người dùng, tài liệu và hiệu suất hệ thống.
- 🎨 **UI/UX Tối giản:** Sử dụng font chữ chuyên dụng hỗ trợ tiếng Việt (Inter, Be Vietnam Pro) và Markdown rendering sắc nét.

## 🛠️ Tech Stack

- **Backend:** FastAPI, Python 3.11.
- **Vector DB:** Qdrant Cloud.
- **LLM Engine:** Groq (Llama 3.3 70B).
- **Embedding Engine:** **FastEmbed** (Siêu nhẹ, tối ưu cho RAM 512MB).
- **Task Queue:** Celery + Redis (Upstash) để xử lý nạp tài liệu ngầm.
- **Database:** PostgreSQL (Supabase).
- **Frontend:** HTML5, Vanilla CSS, JavaScript.

## 🚀 Khởi động nhanh (Local)

1. **Chuẩn bị file `.env`:**
   ```env
   GROQ_API_KEY=your_key
   QDRANT_HOST=your_cloud_host
   QDRANT_API_KEY=your_cloud_key
   DATABASE_URL=postgresql://...
   REDIS_URL=redis://localhost:6379/0
   ADMIN_PASSWORD=your_secure_pass
   ```

2. **Chạy bằng Docker Compose:**
   ```bash
   docker-compose up --build
   ```

3. **Truy cập:**
   - App: `http://localhost:8000`
   - Admin: `http://localhost:8000/admin.html`

## 🌍 Triển khai Production

Chi tiết hướng dẫn triển khai hoàn toàn miễn phí trên **Render** kết hợp với **Supabase & Upstash** có thể xem tại:
👉 [Hướng dẫn Triển khai Chi tiết (A-Z)](DEPLOY.md)

---
*Phát triển bởi Crowz. 🚑🏁*
