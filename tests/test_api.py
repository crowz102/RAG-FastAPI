"""
API Tests for RAG Chatbot — using pytest + httpx
Run: pytest tests/ -v
"""
import pytest
import httpx

BASE_URL = "http://localhost:8000"


# ── FIXTURES ──

@pytest.fixture
def client():
    """HTTP client dùng chung cho tất cả test."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as c:
        yield c


@pytest.fixture
def sample_pdf_bytes():
    """Tạo một PDF đơn giản để test upload — không cần file thật."""
    # PDF tối giản hợp lệ với 1 dòng text
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font "
        b"/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td "
        b"(Test document for RAG) Tj ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f\n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n0\n%%EOF"
    )


# ── HEALTH CHECK ──

class TestHealthCheck:

    def test_root_returns_200(self, client):
        """Server phải đang chạy và trả về 200."""
        res = client.get("/")
        assert res.status_code == 200

    def test_root_returns_message(self, client):
        """Response phải có field 'message'."""
        res = client.get("/")
        data = res.json()
        assert "message" in data

    def test_docs_accessible(self, client):
        """Swagger UI phải accessible."""
        res = client.get("/docs")
        assert res.status_code == 200


# ── INGEST ──

class TestIngest:

    def test_ingest_rejects_non_pdf(self, client):
        """Chỉ chấp nhận file PDF, từ chối file khác."""
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        res = client.post("/ingest", files=files)
        assert res.status_code == 400
        assert "PDF" in res.json()["detail"]

    def test_ingest_rejects_empty_file(self, client):
        """File rỗng phải bị từ chối."""
        files = {"file": ("empty.pdf", b"", "application/pdf")}
        res = client.post("/ingest", files=files)
        assert res.status_code == 400

    def test_ingest_valid_pdf_returns_correct_schema(self, client, sample_pdf_bytes):
        """PDF hợp lệ phải trả về đúng schema."""
        files = {"file": ("test.pdf", sample_pdf_bytes, "application/pdf")}
        res = client.post("/ingest", files=files)
        # 200 hoặc 422 (PDF không có text) đều acceptable
        assert res.status_code in (200, 422)
        if res.status_code == 200:
            data = res.json()
            assert "chunks_stored" in data
            assert "filename" in data
            assert data["filename"] == "test.pdf"


# ── CHAT ──

class TestChat:

    def test_chat_returns_correct_schema(self, client):
        """Response phải có đủ các field cần thiết."""
        payload = {
            "question": "test question",
            "session_id": "test-session-schema",
            "top_k": 3
        }
        res = client.post("/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert "session_id" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_chat_session_id_matches(self, client):
        """session_id trong response phải khớp với request."""
        session_id = "test-session-match"
        payload = {"question": "hello", "session_id": session_id, "top_k": 3}
        res = client.post("/chat", json=payload)
        assert res.status_code == 200
        assert res.json()["session_id"] == session_id

    def test_chat_default_top_k(self, client):
        """Không truyền top_k thì vẫn phải chạy được (dùng default)."""
        payload = {"question": "test", "session_id": "test-default-topk"}
        res = client.post("/chat", json=payload)
        assert res.status_code == 200

    def test_chat_creates_session(self, client):
        """Sau khi chat, session phải xuất hiện trong danh sách sessions."""
        session_id = "test-session-create"
        payload = {"question": "does this session get created?", "session_id": session_id}
        client.post("/chat", json=payload)

        res = client.get("/sessions")
        assert res.status_code == 200
        session_ids = [s["id"] for s in res.json()]
        assert session_id in session_ids


# ── HISTORY ──

class TestHistory:

    def test_history_empty_for_new_session(self, client):
        """Session mới chưa có tin nhắn phải trả về list rỗng."""
        res = client.get("/history/nonexistent-session-xyz")
        assert res.status_code == 200
        assert res.json()["messages"] == []

    def test_history_saves_messages(self, client):
        """Sau khi chat, lịch sử phải được lưu đúng."""
        session_id = "test-history-save"
        question = "what is RAG?"

        client.post("/chat", json={"question": question, "session_id": session_id})

        res = client.get(f"/history/{session_id}")
        assert res.status_code == 200
        messages = res.json()["messages"]
        assert len(messages) >= 2  # ít nhất 1 user + 1 assistant

        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_history_user_message_matches(self, client):
        """Tin nhắn user trong history phải khớp với câu hỏi đã gửi."""
        session_id = "test-history-content"
        question = "unique question abc123"

        client.post("/chat", json={"question": question, "session_id": session_id})

        res = client.get(f"/history/{session_id}")
        messages = res.json()["messages"]
        user_messages = [m["content"] for m in messages if m["role"] == "user"]
        assert question in user_messages

    def test_delete_history(self, client):
        """Xóa session thì history phải biến mất."""
        session_id = "test-delete-session"
        client.post("/chat", json={"question": "to be deleted", "session_id": session_id})

        del_res = client.delete(f"/history/{session_id}")
        assert del_res.status_code == 200

        res = client.get(f"/history/{session_id}")
        assert res.json()["messages"] == []


# ── SESSIONS ──

class TestSessions:

    def test_sessions_returns_list(self, client):
        """GET /sessions phải trả về list."""
        res = client.get("/sessions")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_session_has_required_fields(self, client):
        """Mỗi session phải có id, title, created_at."""
        session_id = "test-session-fields"
        client.post("/chat", json={"question": "field test", "session_id": session_id})

        res = client.get("/sessions")
        sessions = {s["id"]: s for s in res.json()}

        if session_id in sessions:
            s = sessions[session_id]
            assert "id" in s
            assert "title" in s
            assert "created_at" in s

    def test_session_title_from_first_question(self, client):
        """Title của session phải lấy từ câu hỏi đầu tiên."""
        session_id = "test-session-title"
        question = "what is vector database?"

        client.post("/chat", json={"question": question, "session_id": session_id})

        res = client.get("/sessions")
        sessions = {s["id"]: s for s in res.json()}

        if session_id in sessions:
            title = sessions[session_id]["title"]
            # Title phải là prefix của câu hỏi
            assert question.startswith(title.rstrip("..."))