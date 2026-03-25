import fitz  # pymupdf
import uuid
import re
import io
import docx
from bs4 import BeautifulSoup
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from app.core.config import QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME, EMBEDDING_MODEL

embedder = SentenceTransformer(EMBEDDING_MODEL)
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection():
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def clean_text(text: str) -> str:
    """Dọn dẹp text: bỏ khoảng trắng thừa, gộp dòng bị xuống hàng giữa câu."""
    # Gộp các dòng bị wrap (dòng không kết thúc bằng dấu câu)
    text = re.sub(r'(?<![.!?:\n])\n(?![•\-\n])', ' ', text)
    # Nhiều khoảng trắng → 1
    text = re.sub(r' {2,}', ' ', text)
    # Nhiều dòng trống → 2 dòng
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def chunk_by_paragraph(text: str, max_chars: int = 800, overlap_chars: int = 100) -> list[str]:
    """
    Chunk theo đoạn văn (paragraph) thay vì đếm ký tự cứng.
    Gộp các đoạn ngắn lại với nhau cho đủ max_chars.
    Nếu 1 đoạn quá dài thì mới cắt theo câu.
    """
    # Tách theo đoạn (2+ newline)
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        # Nếu đoạn này quá dài, cắt theo câu
        if len(para) > max_chars:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sent in sentences:
                if len(current) + len(sent) <= max_chars:
                    current += " " + sent if current else sent
                else:
                    if current:
                        chunks.append(current.strip())
                    current = sent
        else:
            if len(current) + len(para) <= max_chars:
                current += "\n\n" + para if current else para
            else:
                if current:
                    chunks.append(current.strip())
                # Overlap: lấy ~overlap_chars cuối của chunk trước
                overlap = current[-overlap_chars:] if len(current) > overlap_chars else current
                current = overlap + "\n\n" + para if overlap else para

    if current:
        chunks.append(current.strip())

    return chunks


def delete_existing_chunks(filename: str):
    """Xóa toàn bộ chunks cũ của file này trước khi ingest lại."""
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
        ),
    )


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower()
    if ext.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif ext.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif ext.endswith(".html"):
        return extract_text_from_html(file_bytes)
    else:
        raise ValueError("Định dạng file không được hỗ trợ.")

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_html(file_bytes: bytes) -> str:
    soup = BeautifulSoup(file_bytes, "html.parser")
    return soup.get_text(separator="\n")

def ingest_doc(file_bytes: bytes, filename: str) -> int:
    ensure_collection()

    # Xóa chunks cũ nếu file đã được ingest trước đó → tránh duplicate
    delete_existing_chunks(filename)

    text = extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError(f"Không đọc được text từ file: {filename}")

    text = clean_text(text)
    chunks = chunk_by_paragraph(text)

    if not chunks:
        raise ValueError("Không tạo được chunks từ tài liệu này.")

    vectors = embedder.encode(chunks, show_progress_bar=False).tolist()

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": chunk,
                "filename": filename,
                "chunk_index": i,
            },
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)
