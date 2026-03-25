from groq import AsyncGroq
from app.core.config import GROQ_API_KEY

client = AsyncGroq(api_key=GROQ_API_KEY)


def build_messages(question: str, contexts: list[dict], history: list[dict]) -> list[dict]:
    """
    Xây dựng danh sách messages cho Groq API theo chuẩn multi-turn conversation.
    - System prompt: hướng dẫn LLM chỉ dùng context, không bịa
    - History: N tin nhắn gần nhất để LLM nhớ ngữ cảnh
    - User message cuối: context + câu hỏi hiện tại
    """
    context_text = "\n\n---\n\n".join(
        f"[Nguồn: {c['filename']}]\n{c['text']}" for c in contexts
    )

    system_prompt = """Bạn là chuyên gia phân tích và tìm kiếm thông tin tài liệu.
Hãy phân tích câu hỏi, trích xuất các ý chính từ {TÀI LIỆU THAM KHẢO} và suy luận từng bước (Chain of Thought) để đưa ra câu trả lời chi tiết.
Quy tắc BẮT BUỘC:
1. TRẢ LỜI DỰA HOÀN TOÀN VÀ DUY NHẤT VÀO TÀI LIỆU CUNG CẤP.
2. NẾU KHÔNG CÓ THÔNG TIN TRONG TÀI LIỆU, hãy trả lời chính xác: "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong các tài liệu đã cung cấp." Tuyệt đối không bịa đặt hoặc dùng kiến thức ngoài lề.
3. LUÔN trích dẫn nguồn (tên file) mỗi khi đưa ra một luận điểm cụ thể. VD: (Nguồn: thong_bao_a.pdf).
4. Sử dụng lịch sử trò chuyện để hiểu rõ ngữ cảnh của đại từ (vd: "nó", "nhân vật này").
5. Trình bày bằng cấu trúc rõ ràng (Dùng markdown bullet list/bold)."""

    messages = [{"role": "system", "content": system_prompt}]

    # Thêm N tin nhắn gần nhất từ history (tối đa 10 để không quá dài)
    recent_history = history[-10:] if len(history) > 10 else history
    for msg in recent_history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    # Tin nhắn hiện tại: ghép context + câu hỏi
    if context_text:
        user_content = f"""=== TÀI LIỆU THAM KHẢO ===
{context_text}

=== CÂU HỎI ===
{question}"""
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})
    return messages


async def generate_answer_stream(question: str, contexts: list[dict], history: list[dict] = None):
    """Gọi Groq với stream=True"""
    if history is None:
        history = []

    if not contexts:
        yield "Không tìm thấy tài liệu liên quan. Vui lòng upload tài liệu trước."
        return

    messages = build_messages(question, contexts, history)

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