from groq import AsyncGroq
from app.core.config import GROQ_API_KEY
from app.db.database import get_setting

import httpx
_groq_clients = {}
_httpx_client = None

def get_httpx_client():
    global _httpx_client
    if _httpx_client is None or _httpx_client.is_closed:
        _httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
    return _httpx_client

async def get_groq_client(user_api_key: str = None) -> AsyncGroq:
    api_key = None
    if user_api_key and user_api_key.strip():
        api_key = user_api_key.strip()
    else:
        api_key = get_setting("GROQ_API_KEY") or GROQ_API_KEY

    if not api_key:
        raise ValueError("Lỗi cấu hình: Administrator chưa thiết lập Groq API Key.")
        
    if api_key not in _groq_clients:
        # Create AsyncGroq with our shared httpx client
        _groq_clients[api_key] = AsyncGroq(
            api_key=api_key,
            http_client=get_httpx_client()
        )
        
    return _groq_clients[api_key]


def build_messages(question: str, contexts: list[dict], history: list[dict]) -> list[dict]:
    # Lấy 6 tin nhắn chat gần nhất để tránh model bị quá tải context
    recent_history = history[-6:] if len(history) > 6 else history

    messages = [{"role": m["role"], "content": m["content"]} for m in recent_history]

    context_text = "\n\n---\n\n".join(
        f"[Nguồn: {c['filename']}, Trang: {c.get('page', 1)}]\n{c['text']}" for c in contexts
    )

    system_prompt = """Bạn là chuyên gia máy tính thông thái có nhiệm vụ phân tích tài liệu và trò chuyện với người dùng.
Hãy suy luận từng bước (Chain of Thought) để đưa ra câu trả lời chi tiết và chính xác nhất.
Quy tắc BẮT BUỘC:
1. TRẢ LỜI DỰA VÀO TÀI LIỆU CUNG CẤP. Ưu tiên thông tin trong tài liệu hơn kiến thức chung.
2. NẾU CÂU HỎI KHÔNG CÓ TRONG TÀI LIỆU, hãy trả lời: "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong các tài liệu đã cung cấp." (Tuy nhiên, nếu là câu chào hỏi xã giao, hãy phản hồi thân thiện).
3. LUÔN trích dẫn nguồn bao gồm Tên file và Số trang ngay bên cạnh thông tin trích dẫn. VD: (Nguồn: thong_bao_a.pdf, Trang 3).
4. Sử dụng lịch sử trò chuyện để hiểu rõ ngữ cảnh.
5. Trình bày bằng Markdown (Sử dụng Bold, Bullet points, hoặc Bảng nếu dữ liệu phức tạp)."""

    messages.insert(0, {"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": f"TÀI LIỆU THAM KHẢO:\n{context_text}\n\nCâu hỏi: {question}"})

    return messages


async def contextualize_question(question: str, history: list[dict], api_key: str = None) -> str:
    """Viết lại câu hỏi dựa trên lịch sử để tạo thành câu hỏi độc lập (Standalone Question) dùng cho Vector Search."""
    if not history:
        return question
        
    system_prompt = """Dựa vào lịch sử trò chuyện và câu hỏi mới nhất của người dùng, việc của bạn là viết lại câu hỏi để có thể hiểu được hoàn toàn độc lập mà không cần lịch sử, nhưng vẫn giữ nguyên ý nghĩa ban đầu.
Nhiệm vụ là tạo câu hỏi tìm kiếm (Search Query) chuẩn xác nhất cho cơ sở dữ liệu Vector.
Chỉ trả về DUY NHẤT nội dung câu hỏi đã viết lại, tuyệt đối không giải thích thêm. Nếu câu hỏi đã độc lập sẵn hoặc là câu chào hỏi, trả về nguyên bản."""
    
    # Lấy 4 tin nhắn gần nhất để làm context nhanh
    recent_history = history[-4:]
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in recent_history])
    
    prompt = f"Lịch sử:\n{history_text}\n\nCâu hỏi mới: {question}\n\nViết lại câu hỏi:"
    
    try:
        from app.db.database import increment_setting
        client = await get_groq_client(api_key)
        increment_setting("groq_api_calls", 1)  # Track telemetry
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=64
        )
        rewritten = response.choices[0].message.content.strip()
        # Loại bỏ ngoặc kép nếu LLM tự thêm
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        return rewritten
    except Exception:
        return question


async def generate_answer_stream(question: str, contexts: list[dict], history: list[dict] = None, api_key: str = None):
    """Gọi Groq với stream=True"""
    if history is None:
        history = []

    if not contexts:
        yield "Không tìm thấy tài liệu liên quan. Vui lòng upload tài liệu trước."
        return

    messages = build_messages(question, contexts, history)

    try:
        from app.db.database import increment_setting
        client = await get_groq_client(api_key)
        increment_setting("groq_api_calls", 1)  # Track telemetry
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
            stream=True
        )

        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        yield f"Lỗi gọi AI: {str(e)}"