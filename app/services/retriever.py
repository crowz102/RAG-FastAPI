from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchText, MatchValue
from app.core.config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, COLLECTION_NAME, EMBEDDING_MODEL
from app.services.ingest import get_embedder

# Re-ranking is disabled to save RAM on Render Free Tier

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

    # 4. Re-ranking (Tạm thời tắt để tiết kiệm RAM trên Render Free)
    for doc in documents:
        doc["cross_score"] = doc["qdrant_score"]

    documents.sort(key=lambda x: x["qdrant_score"], reverse=True)
    return documents[:top_k]
