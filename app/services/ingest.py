import fitz  # pymupdf
import uuid
import re
import io
import docx
from bs4 import BeautifulSoup
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from fastembed import TextEmbedding
from app.core.config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, COLLECTION_NAME, EMBEDDING_MODEL

# Global variable to hold the embedder instance
_embedder = None

_client = None

def get_embedder():
    global _embedder
    if _embedder is None:
        print(f"📥 Loading FastEmbed Model: {EMBEDDING_MODEL}...")
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _embedder

def get_qdrant_client():
    global _client
    if _client is None:
        if "cloud.qdrant.io" in QDRANT_HOST:
            # Cloud Cluster: use URL + API KEY
            url = f"https://{QDRANT_HOST}"
            _client = QdrantClient(url=url, api_key=QDRANT_API_KEY, timeout=60)
        else:
            # Local Docker: use host + port
            _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _client


def ensure_collection():
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        # Tạo Full-text Index cho trường text để hỗ trợ Hybrid Search
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="text",
            field_schema="text",
        )
        print(f"🚀 Đã khởi tạo Collection {COLLECTION_NAME} với Full-text Index.")
    
    # Kiểm tra và tạo Payload Index cho 'text' nếu chưa có (cho những collection cũ)
    info = client.get_collection(COLLECTION_NAME)
    indexed_fields = info.payload_schema if info.payload_schema else {}
    if "text" not in indexed_fields:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="text",
            field_schema="text",
        )
        print(f"🔍 Đã bổ sung Full-text Index cho trường 'text' của {COLLECTION_NAME}.")
        
    if "user_id" not in indexed_fields:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="user_id",
            field_schema="keyword",
        )
        print(f"🔍 Đã bổ sung Keyword Index cho trường 'user_id' của {COLLECTION_NAME}.")
        
    if "filename" not in indexed_fields:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="filename",
            field_schema="keyword",
        )
        print(f"🔍 Đã bổ sung Keyword Index cho trường 'filename' của {COLLECTION_NAME}.")


def extract_text_from_pdf(file_bytes: bytes) -> list[dict]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({"text": text, "page": i + 1})
    return pages


def clean_text(text: str) -> str:
    """Dọn dẹp text: bỏ khoảng trắng thừa, gộp dòng bị xuống hàng giữa câu."""
    # Gộp các dòng bị wrap (dòng không kết thúc bằng dấu câu)
    text = re.sub(r'(?<![.!?:\n])\n(?![•\-\n])', ' ', text)
    # Nhiều khoảng trắng → 1
    text = re.sub(r' {2,}', ' ', text)
    # Nhiều dòng trống → 2 dòng
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def chunk_by_paragraph(paragraphs_with_meta: list[dict], max_chars: int = 800, overlap_chars: int = 200) -> list[dict]:
    """
    paragraphs_with_meta: list [{"text": str, "page": int}]
    Returns: list [{"text": str, "page": int}]
    """
    chunks = []
    current_text = ""
    current_page = None

    for item in paragraphs_with_meta:
        text = item["text"]
        page = item.get("page")
        
        # Tách nhỏ hơn nữa nếu đoạn quá dài
        sub_paras = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        
        for para in sub_paras:
            if current_page is None:
                current_page = page

            if len(para) > max_chars:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in sentences:
                    if len(current_text) + len(sent) <= max_chars:
                        current_text += " " + sent if current_text else sent
                    else:
                        if current_text:
                            chunks.append({"text": current_text.strip(), "page": current_page})
                        current_text = sent
                        current_page = page
            else:
                if len(current_text) + len(para) <= max_chars:
                    current_text += "\n\n" + para if current_text else para
                else:
                    if current_text:
                        chunks.append({"text": current_text.strip(), "page": current_page})
                    # Overlap
                    overlap = current_text[-overlap_chars:] if len(current_text) > overlap_chars else current_text
                    current_text = overlap + "\n\n" + para
                    current_page = page

    if current_text:
        chunks.append({"text": current_text.strip(), "page": current_page})

    return chunks


def delete_existing_chunks(filename: str, user_id: str):
    """Xóa toàn bộ chunks cũ của file này của User này trước khi ingest lại."""
    try:
        client = get_qdrant_client()
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(key="filename", match=MatchValue(value=filename)),
                    FieldCondition(key="user_id", match=MatchValue(value=user_id))
                ]
            ),
        )
    except Exception as e:
        # Bỏ qua nếu collection chưa tồn tại hoặc không tìm thấy file
        pass


def extract_text_with_meta(file_bytes: bytes, filename: str) -> list[dict]:
    ext = filename.lower()
    if ext.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    
    # Docx/Html tam thoi chua support Page Number vi tinh chat flowable
    content = ""
    if ext.endswith(".docx"):
        content = extract_text_from_docx(file_bytes)
    elif ext.endswith(".html"):
        content = extract_text_from_html(file_bytes)
    else:
        raise ValueError("Định dạng file không được hỗ trợ.")
    return [{"text": content, "page": 1}]

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_html(file_bytes: bytes) -> str:
    soup = BeautifulSoup(file_bytes, "html.parser")
    return soup.get_text(separator="\n")

def ingest_doc(file_bytes: bytes, filename: str, user_id: str) -> int:
    ensure_collection()

    # Xóa chunks cũ nếu file đã được ingest trước đó bởi User này
    delete_existing_chunks(filename, user_id)

    # 1. Trích xuất text kèm Metadata
    text_meta = extract_text_with_meta(file_bytes, filename)
    if not text_meta:
        raise ValueError(f"Không đọc được text từ file: {filename}")

    # 2. Chunking thông minh kèm Metadata
    chunks_meta = chunk_by_paragraph(text_meta)

    if not chunks_meta:
        raise ValueError("Không tạo được chunks từ tài liệu này.")

    # 3. Embedding (FastEmbed returns an iterator)
    embedder = get_embedder()
    texts_only = [c["text"] for c in chunks_meta]
    vectors = list(embedder.embed(texts_only))

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": item["text"],
                "filename": filename,
                "user_id": user_id,
                "page": item["page"],
                "chunk_index": i,
            },
        )
        for i, (item, vector) in enumerate(zip(chunks_meta, vectors))
    ]

    client = get_qdrant_client()
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)
