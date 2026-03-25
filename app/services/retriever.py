from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchText, MatchValue
from sentence_transformers import CrossEncoder
from app.core.config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, COLLECTION_NAME, EMBEDDING_MODEL
from app.services.ingest import get_embedder

# Pre-load Models at Module Level to avoid latency on first request
_cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
_client = None

def get_cross_encoder():
    return _cross_encoder

def get_qdrant_client():
    global _client
    if _client is None:
        if "cloud.qdrant.io" in QDRANT_HOST:
            url = f"https://{QDRANT_HOST}"
            _client = QdrantClient(url=url, api_key=QDRANT_API_KEY, timeout=60)
        else:
            _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)
    return _client

import asyncio

async def retrieve(question: str, top_k: int = 5, filenames: list[str] = None, user_id: str = None) -> list[dict]:
    # 1. Embedding câu hỏi (FastEmbed returns an iterator of arrays)
    embedder = get_embedder()
    query_vector = list(embedder.embed([question]))[0].tolist()

    must_conditions = []
    if user_id:
        must_conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
    if filenames:
        must_conditions.append(FieldCondition(key="filename", match=MatchAny(any=filenames)))

    query_filter = Filter(must=must_conditions) if must_conditions else None
    # 1 & 2. Search logic (Bọc try-except để tránh sập Server 500 khi có sự cố mạng hoặc Collection Cloud chưa sẵn sàng)
    vector_results = []
    text_results = []
    try:
        client = get_qdrant_client()
        # 1. Vector Search
        vector_results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k * 2,
            with_payload=True,
        ).points

        # 2. Full-Text Search
        text_results = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="text", match=MatchText(text=question))
                ] + must_conditions
            ),
            limit=top_k * 2,
            with_payload=True,
        )[0]
    except Exception as e:
        import traceback
        print(f"❌ LỖI TRUY VẤN QDRANT CLOUD: {str(e)}")
        # print(traceback.format_exc()) # Bỏ comment nếu muốn xem chi tiết hơn
        return []

    # 3. Merge & Deduplicate
    seen_ids = set()
    documents = []
    for hit in vector_results + text_results:
        if hit.id not in seen_ids:
            score = getattr(hit, 'score', 0.0)
            documents.append({
                "text": hit.payload["text"],
                "filename": hit.payload.get("filename", "unknown"),
                "page": hit.payload.get("page", 1),
                "qdrant_score": round(score, 4) if score else 0.0,
            })
            seen_ids.add(hit.id)

    if not documents:
        return []

    # 4. Re-ranking
    try:
        cross_inp = [[question, doc["text"]] for doc in documents]
        cross_encoder = get_cross_encoder()
        cross_scores = await asyncio.to_thread(cross_encoder.predict, cross_inp)

        for idx, score in enumerate(cross_scores):
            documents[idx]["cross_score"] = float(score)

        documents.sort(key=lambda x: x["cross_score"], reverse=True)
    except Exception as e:
        print(f"⚠️ Lỗi Re-ranking (Sẽ dùng kết quả Vector gốc): {str(e)}")
        for doc in documents:
            doc["cross_score"] = doc["qdrant_score"]

    return documents[:top_k]
