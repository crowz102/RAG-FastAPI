# RAG Chatbot API

Backend hệ thống hỏi đáp thông minh dựa trên tài liệu PDF, sử dụng RAG (Retrieval-Augmented Generation) với FastAPI, Qdrant và Gemini AI.

## Tech Stack

- **FastAPI** — RESTful API backend
- **Qdrant** — Vector database cho semantic search
- **Sentence Transformers** — Embedding model (`all-MiniLM-L6-v2`)
- **Google Gemini 1.5 Flash** — LLM tạo câu trả lời
- **PyMuPDF** — Đọc và trích xuất text từ PDF

## Kiến trúc RAG Pipeline

```
Upload PDF
    ↓
Trích xuất text (PyMuPDF)
    ↓
Chia chunk (500 ký tự, overlap 50)
    ↓
Embedding (Sentence Transformers)
    ↓
Lưu vào Qdrant

──── Khi user hỏi ────

Câu hỏi → Embed → Similarity Search (Qdrant) → Top-K chunks
    ↓
Ghép vào RAG Prompt
    ↓
Gemini API → Câu trả lời
    ↓
Lưu lịch sử hội thoại (theo session)
```

## Cài đặt và Chạy

### 1. Clone và setup môi trường

```bash
git clone <repo-url>
cd rag-fastapi

python -m venv venv
venv\Scripts\activate   # Windows
# hoặc: source venv/bin/activate  (Linux/macOS)

pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường

Tạo file `.env`:

```env
GROQ_API_KEY=your_api_key_here
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

Lấy Groq API key miễn phí tại: https://groq.com/

### 3. Chạy Qdrant bằng Docker

```bash
docker run -d -p 6333:6333 -p 6334:6334 --name qdrant qdrant/qdrant
```

### 4. Chạy server

```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/ingest` | Upload PDF, tự động chunk và lưu vào Qdrant |
| POST | `/chat` | Hỏi đáp dựa trên tài liệu đã upload |
| GET | `/history/{session_id}` | Lấy lịch sử hội thoại |
| DELETE | `/history/{session_id}` | Xóa lịch sử hội thoại |

### Ví dụ sử dụng

**Upload tài liệu:**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf"
```

**Hỏi đáp:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Nội dung chính của tài liệu là gì?", "session_id": "user_1"}'
```

**Xem lịch sử:**
```bash
curl http://localhost:8000/history/user_1
```