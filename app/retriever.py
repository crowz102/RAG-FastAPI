from qdrant_client import QdrantClient
from app.config import QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME
from app.ingest import embedder  # Dùng chung instance để không load model 2 lần

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def retrieve(question: str, top_k: int = 5) -> list[dict]:
    """
    Embed câu hỏi → tìm top_k chunks gần nhất trong Qdrant.
    Trả về list dict gồm text và filename.
    """
    query_vector = embedder.encode(question).tolist()

    # Qdrant client v1.7.3+ dùng query_points thay vì search
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    ).points

    return [
        {
            "text": hit.payload["text"],
            "filename": hit.payload.get("filename", "unknown"),
            "score": round(hit.score, 4),
        }
        for hit in results
    ]