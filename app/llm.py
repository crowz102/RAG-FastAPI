from groq import Groq
from app.config import GROQ_API_KEY


client = Groq(api_key=GROQ_API_KEY)


def build_prompt(question: str, contexts: list[dict]) -> str:
    context_text = "\n\n---\n\n".join(
        f"[Nguồn: {c['filename']}]\n{c['text']}" for c in contexts
    )

    return f"""Bạn là trợ lý AI thông minh. Hãy trả lời câu hỏi dựa HOÀN TOÀN vào các đoạn tài liệu được cung cấp bên dưới.

Nếu câu trả lời không có trong tài liệu, hãy nói rõ "Tôi không tìm thấy thông tin này trong tài liệu được cung cấp." Không được bịa thêm thông tin.

=== TÀI LIỆU THAM KHẢO ===
{context_text}

=== CÂU HỎI ===
{question}

=== TRẢ LỜI ==="""


def generate_answer(question: str, contexts: list[dict]) -> str:
    """Gọi Groq (Llama 3.3 70b) với RAG prompt và trả về câu trả lời."""
    if not contexts:
        return "Không tìm thấy tài liệu liên quan. Vui lòng upload tài liệu trước."

    prompt = build_prompt(question, contexts)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,  # thấp để câu trả lời bám sát tài liệu
        max_tokens=1024,
    )

    return response.choices[0].message.content